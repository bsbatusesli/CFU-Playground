#!/bin/env python
# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from amaranth_cfu import all_words, InstructionBase, InstructionTestBase, pack_vals, simple_cfu, Cfu, CfuTestBase,TestBase, SimpleElaboratable
from amaranth import *
from amaranth.back import verilog
from amaranth.sim import Delay, Simulator, Tick
import re, unittest

class SIMD8_StoreCodebook_Instruction(InstructionBase):
  # Instruction for Storing Codebook
  # This instruction is independent from funct7 value
  # It splits the value on in1 line to 4 x 8 bit signed clusters
  # clus0 in[0:8] 
  def __init__(self):
    super().__init__()
    self.clusters = Signal(32)

  def elab(self, m):
    cluster = lambda s: all_words(s, 8)

    m.d.sync += self.clusters.eq(self.clusters)

    with m.If(self.start):
      for clus, value in zip(cluster(self.clusters), cluster(self.in1)):
          m.d.sync += clus.eq(value.as_signed())

      m.d.comb += [
                self.done.eq(1),
                self.output.eq(1),
            ]
    
    return m
      


class SIMD8_StoreCodebook_Instruction_Test(InstructionTestBase):
  def create_dut(self):
    return SIMD8_StoreCodebook_Instruction()
  
  def test(self):
    DATA = [
        # (( start, in1) , (done, output, clusters) )

        #set weights 0 
        ((1,0), (1, 1, 0)), 
        #set cluster values
        ((1,0x12FAD87E), (1,1,0x12FAD87E)),
        #Check that when start is 0, clusters remains same
        ((0,0xFFFFFFFF), (0,0,0x12FAD87E)),
        ((0,0xFFFADBCD), (0,0,0x12FAD87E)),
    ]
    def process():
            for n, (inputs, outputs) in enumerate(DATA):
                start, in1 = inputs
                done, output, clusters = outputs
                yield self.dut.start.eq(start)
                yield self.dut.in1.eq(in1)
                yield
                yield
                self.assertEqual((yield self.dut.done), done)
                self.assertEqual((yield self.dut.output), output)
                self.assertEqual((yield self.dut.clusters), clusters)

    self.run_sim(process, False)
    




class SIMD8_Weights_Instruction(InstructionBase):
  # Instruction for Managing Weights
  # It should first stores codes. It has memory for storing 32 weight codes
  # then it decodes the codes by looking at Codebook. In each cycle, only 8 weight can be pushed to the pipelin
  # Those 8 weights controlled by funct 7 last 2 bits funct[0:2] values:(0,1,2,3)  

  # 3. Bit enable/disable storing funct[3] (Note: that can be also deleted since it is used only when instruction called)
  # funct7 = |_|_|enableAccumulator|resetAccumulator|storeWeights|control1|control0|
    #mask for funct7
    #storeWeight Enable = 0x100
  

  def __init__(self):
    super().__init__()
    self.clusters = Signal(32)
    self.decoded_weights = Signal(64)
    self.weight_codes = Signal(16)
    self.weights = Signal(64)

  def elab(self, m):
    codes = lambda s: all_words(s, 2)
    weights = lambda s: all_words(s, 8)

    m.d.comb += [ self.weights.eq(self.weights),
                  self.weight_codes.eq(self.weight_codes),
                  self.decoded_weights.eq(self.decoded_weights),
                  #self.output.eq(self.decoded_weights[0:32]) # for testing purposes !!! DELETE after
    ]
    #checks funct7 last 2 bits and assigns weight codes
    with m.Switch(self.funct7[:2]):
      with m.Case(0b00):
        m.d.comb += self.weight_codes.eq(self.weights[0:16])
      with m.Case(0b01):
        m.d.comb += self.weight_codes.eq(self.weights[16:32])
      with m.Case(0b10):
        m.d.comb += self.weight_codes.eq(self.weights[32:48])
      with m.Case(0b11):
        m.d.comb += self.weight_codes.eq(self.weights[48:64])

        # for each weight code (2bit) checks value and assigns its weight
    for code, weight in zip(codes(self.weight_codes), weights(self.decoded_weights)):
      with m.Switch(code):
        with m.Case("00"):
          m.d.comb += weight.eq(self.clusters[0:8])
        with m.Case("01"):
          m.d.comb += weight.eq(self.clusters[8:16])
        with m.Case("10"):
          m.d.comb += weight.eq(self.clusters[16:24])
        with m.Case("11"):
          m.d.comb += weight.eq(self.clusters[24:32])
    
    with m.If(self.start):
        m.d.comb += self.done.eq(1)  # return control to the CPU on next cycle
        #self.output.eq(self.decoded_weights[0:32])

        #enable store new weights MSB In1 In0 LSB
        with m.If(self.funct7 & 0b100):
            m.d.comb += self.weights.eq(Cat([self.in0, self.in1]))
          



class SIMD8_Weights_Instruction_Test(InstructionTestBase):
  def create_dut(self):
    return SIMD8_Weights_Instruction()
  
  def test(self):
    DATA = [
        # ( (start, func7, in0, in1, clusters) , (done, weights, weight_codes, decoded_weights) )

      # store weight codes
      # First slot : 0xFA32 = 11_11_10_10_00_11_00_10 |||| Second slot:   0x01FF = 00_00_00_01_11_11_11_11
      # Third Slot:  0x547A= 01_01_01_00_01_11_10_10  |||| Fourth slot :  0x12ED= 00_01_00_10_11_10_11_01

      ((1, 0b0000100, 0x01FFFA32, 0x12ED547A, 0xAABBCCDD),(1, 0x12ED547A01FFFA32, None, None)),
      #check outputs remain same when start is 0, and other func7 values
      ((0, 0b0000100, 0xFFFFFFFF, 0xFFFFFFFF, 0xAABBCCDD),(0, 0x12ED547A01FFFA32, None, None)),
      ((1, 0b0011011, 0xFFFFFFFF, 0xFFFFFFFF, 0xAABBCCDD),(1, 0x12ED547A01FFFA32, None, None)),
      ((1, 0b1111000, 0xFFFFFFFF, 0xFFFFFFFF, 0xAABBCCDD),(1, 0x12ED547A01FFFA32, None, None)),
      #check slots and decoding value
      ((1, 0b0000000, 0x01FFFA32, 0x12ED547A, 0xAABBCCDD),(1, 0x12ED547A01FFFA32, 0xFA32, 0xAAAABBBBDDAADDBB)),
      ((1, 0b0000001, 0x01FFFA32, 0x12ED547A, 0xAABBCCDD),(1, 0x12ED547A01FFFA32, 0x01FF, 0xDDDDDDCCAAAAAAAA)),
      ((1, 0b0000010, 0x01FFFA32, 0x12ED547A, 0xAABBCCDD),(1, 0x12ED547A01FFFA32, 0x547A, 0xCCCCCCDDCCAABBBB)),
      ((1, 0b0000011, 0x01FFFA32, 0x12ED547A, 0xAABBCCDD),(1, 0x12ED547A01FFFA32, 0x12ED, 0xDDCCDDBBAABBAACC)),
      


    ]
    
    def process():
      for n, (inputs, outputs) in enumerate(DATA):
        start, funct7, in0, in1, clusters = inputs
        done, weights, weight_codes, decoded_weights = outputs
        yield self.dut.start.eq(start)
        yield self.dut.in0.eq(in0)
        yield self.dut.in1.eq(in1)
        yield self.dut.clusters.eq(clusters)
        yield self.dut.funct7.eq(funct7)
        yield
        self.assertEqual((yield self.dut.done), done)
        self.assertEqual((yield self.dut.weights), weights)
        if weight_codes is not None :   self.assertEqual((yield self.dut.weight_codes), weight_codes)
        if decoded_weights is not None: self.assertEqual((yield self.dut.decoded_weights), decoded_weights)

    self.run_sim(process, False)




class SIMD8_MAC_Instruction(InstructionBase):
  #Instruction for accumulating stored and decoded weight with incoming inputs.
  # Inputs splits 8bit words, in total 8x8bit filter values, each cycle only 8 MAC can be computed.
  # Output occurs in next clock cycle

  #Value of Funct7 determines the functionality
  # funct7 = |_|_|enableAccumulator|resetAccumulator|storeWeights|control1|control0|
  # masks for funct7 used in MAC instruction 
  # enableAccumulator = 0b10000
  # resetAccumulator = 0b1000

  # Control bits should be given properly while calling the instruction. 
  # 00 => Weight 1-8 pushed to the pipeline
  # 01 => Weight 9-15 pushed to the pipeline
  # 10 => Weight 16-23 pushed to the pipeline
  # 11 => Weight 24-32 pushed to the pipeline

  def __init__(self):
    #INPUTS
    super().__init__()
    self.decoded_weights = Signal(64)
    self.acc = Signal(signed(32))

    

  def elab(self, m):

    words = lambda s: all_words(s, 8)

    # SIMD multiply step:
    self.prods_0 = [Signal(signed(32)) for _ in range(4)] # products connected to input line 0
    self.prods_1 = [Signal(signed(32)) for _ in range(4)] # products connected to input line 1

    m.d.comb += self.output.eq(self.acc)
    m.d.sync += self.acc.eq(self.acc) 

    for prod0, prod1, w0, w1, f0, f1 in zip(self.prods_0, self.prods_1, words(self.decoded_weights[0:32]), words(self.decoded_weights[32:64]), words(self.in0), words(self.in1)):
          m.d.comb += [prod0.eq(w0.as_signed() * f0.as_signed()),
                      prod1.eq(w1.as_signed() * f1.as_signed())
                      ]

    #reset accumulator
    with m.If(self.funct7 & 0b1000):
          m.d.sync += self.acc.eq(0) 

    with m.If(self.start):
      m.d.comb += self.done.eq(1)  # return control to the CPU on next cycle

      # Accumulate step:
      with m.If(self.funct7 & 0b10000):
        m.d.sync += [self.acc.eq(self.acc + sum(self.prods_0) + sum(self.prods_1)) ]





class SIMD8_MAC_Instruction_Test(InstructionTestBase):
  def create_dut(self):
    return SIMD8_MAC_Instruction()

  def test(self):

    def signed_pack(*values, bits=8):
        mask = (1 << bits) - 1
        result = 0
        for i, v in enumerate(values):
          if v < 0:
            v = mask + v + 1
          result += (v & mask) << (i * bits)
        return result


    DATA = [
        # ( (start, func7, in0, in1, decoded_weights) , (done, acc, output) )

      #reset accumulator
      ((1, 0b1000, 0x5, 0, 0x2),(1, 0, 0)), 
      # check start
      ((0, 0b10000, 0x5, 0, 0x2),(1, 0, 0)),
      #feed values for accumulation 5x2 
      ((1, 0b10000, 0x5, 0, 0x2),(1, 10, 10)), 
      #second values 3x1
      ((1, 0b10000, 0x3, 0, 0x1),(1, 13, 13)), 
      # reset accumulator
      ((1, 0b1000, 0x3, 0, 0x1),(1, 0, 0)), 
      #enable accumulator again
      ((1, 0b10000, 0x4, 0, 0x3),(1, 12, 12)),
      #read values 
      ((1, 0b0001, 0x45, 0, 0x3),(1, 12, 12)), 
      #enable accumulator
      ((1, 0b10000, 0x4, 0, 0x3),(1, 24, 24)),
      ((1, 0b10000, signed_pack(-5,3,2,56), signed_pack(12,2,4,-9), signed_pack(5,-2,10,8,5,-2,10,8)),(1, 24+461, 24+461)),
      #read values
      ((1, 0b0001, 0, 0, signed_pack(5,-2,10,8,5,-2,10,8)),(1, 24+461, 24+461)),


    ]
    
    def process():
      for n, (inputs, outputs) in enumerate(DATA):
        start, funct7, in0, in1, decoded_weights = inputs
        done, acc, output = outputs
        yield self.dut.start.eq(start)
        yield self.dut.in0.eq(in0)
        yield self.dut.in1.eq(in1)
        yield self.dut.decoded_weights.eq(decoded_weights)
        yield self.dut.funct7.eq(funct7)
        yield
        yield self.dut.start.eq(0)
        yield
        if acc is not None: self.assertEqual((yield self.dut.acc), acc)
        if output is not None :   self.assertEqual((yield self.dut.output), output)
        
        

    self.run_sim(process, False)


    



class SIMD8_CFU(Cfu):
  def elab_instructions(self,m):
    m.submodules["store_codebook"] = store_codebook = SIMD8_StoreCodebook_Instruction()
    m.submodules["weights"] = weights = SIMD8_Weights_Instruction()
    m.submodules["macc"] = macc = SIMD8_MAC_Instruction()

    m.d.comb += [ weights.clusters.eq(store_codebook.clusters),
                 macc.decoded_weights.eq(weights.decoded_weights)
                 ]

    return {
        0: store_codebook,
        1: weights,
        2: macc
    }

class CfuTest(CfuTestBase):
  def create_dut(self):
    return SIMD8_CFU()

  def test(self):
    def signed_pack(*values, bits=8):
        mask = (1 << bits) - 1
        result = 0
        for i, v in enumerate(values):
          if v < 0:
            v = mask + v + 1
          result += (v & mask) << (i * bits)
        return result
    
    functionList = {
      "storeCodebook" : 0,
      "storeWeights" : 0b100,
      "resetAccumulator" : 0b1000,
      "enableAccumulator_weightSet1" : 0b10000,
      "enableAccumulator_weightSet2" : 0b10001,
      "enableAccumulator_weightSet3" : 0b10010,
      "enableAccumulator_weightSet4" : 0b10011,
      "readAccumulator" : 0,
    }



      # ( (function_id, func7 in0, in1) , expected output )
    DATA = [
      # load Storebook
      ((0, functionList["storeCodebook"], 0, 0x04030201), None), 

      # store weight codes 
      ((1,functionList["storeWeights"], 0x01FFFA32, 0x12ED547A), None)  ,     
      # First slot : 0xFA32 = 11_11_10_10_00_11_00_10 |||| Second slot:   0x01FF = 00_00_00_01_11_11_11_11
      # Third Slot:  0x547A= 01_01_01_00_01_11_10_10  |||| Fourth slot :  0x12ED= 00_01_00_10_11_10_11_01


      #reset accumulator
      ((2,functionList["resetAccumulator"], 0, 0), None),

      #check accumulator is zero
      ((2,0, 0, 0), 0),

      #accumulate and read
      ((2,functionList["enableAccumulator_weightSet1"], 0x01010101, 0x01010101), None),
      ((2,functionList["readAccumulator"], 0x01010101, 0x01010101), 3+1+4+1+3+3+4+4),

      #accumulate and read
      ((2,functionList["enableAccumulator_weightSet2"], 0x01010101, 0x01010101), None),
      ((2,functionList["readAccumulator"], 0x01010101, 0x01010101), 3+1+4+1+3+3+4+4+ 1+1+1+2+4+4+4+4),
    ]
    self.run_ops(DATA, write_trace= False)

def make_cfu():
    return SIMD8_CFU()

if __name__ == '__main__':
    unittest.main()
