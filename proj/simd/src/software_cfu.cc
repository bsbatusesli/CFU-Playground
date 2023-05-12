/*
 * Copyright 2021 The CFU-Playground Authors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "software_cfu.h"

#include <stdio.h>
#include <stdint.h>
#include <inttypes.h>


uint32_t clusters = 0;
uint64_t weights = 0;
uint32_t acc = 0;

// Gets a byte as an int8 from the given word
inline int8_t extract_byte(uint32_t word, int8_t num) {
  return static_cast<int8_t>(0xff & (word >> (num * 8)));
}

inline uint8_t extract_codes(uint16_t word, int8_t num) {
  return static_cast<uint8_t>(0b11 & (word >> (num * 2)));
}

inline uint16_t extract_weight_set(uint64_t word, int8_t num) {
  return static_cast<uint16_t>(0xFFFF & (word >> (num * 16)));
}

int32_t multiply_add(uint32_t rs1, uint32_t rs2, uint32_t clus, uint16_t weights_codes) {
    //printf("Multiply and ad started......\nClusters 0x%X\n weights_codes 0x%X\n rs1:0x%X\n rs2:0x%X\n",clus, weights_codes, rs1, rs2);
/*     return (
        (extract_byte(clus, extract_codes(weights_codes, 0)) * extract_byte(rs1, 0)) +
        (extract_byte(clus, extract_codes(weights_codes, 1)) * extract_byte(rs1, 1)) +
        (extract_byte(clus, extract_codes(weights_codes, 2)) * extract_byte(rs1, 2)) +
        (extract_byte(clus, extract_codes(weights_codes, 3)) * extract_byte(rs1, 3)) +
        
        (extract_byte(clus, extract_codes(weights_codes, 4)) * extract_byte(rs2, 0)) +
        (extract_byte(clus, extract_codes(weights_codes, 5)) * extract_byte(rs2, 1)) +
        (extract_byte(clus, extract_codes(weights_codes, 6)) * extract_byte(rs2, 2)) +
        (extract_byte(clus, extract_codes(weights_codes, 7)) * extract_byte(rs2, 3)) 
        ); */
        int32_t sum = 0;
        int8_t value;
        int8_t filter;

        for(int i = 0; i < 4 ; i++) {
            value = extract_byte(clus, extract_codes(weights_codes, i));
            filter = extract_byte(rs1, i);
            printf("RS1 -- cluster value : %d\tfilter value: %d\n", value, filter);
            sum = sum + int32_t(value * filter);

            value = extract_byte(clus, extract_codes(weights_codes, (i+4)));
            filter = extract_byte(rs2, i);
            printf("RS2 -- cluster value : %d\tfilter value: %d\n", value, filter);
            sum = sum + int32_t(value * filter);
            printf("Adding: %ld\n", sum);

        }
        return sum;

}


// In this function, place C code to emulate your CFU. You can switch between
// hardware and emulated CFU by setting the CFU_SOFTWARE_DEFINED DEFINE in
// the Makefile.
uint32_t software_cfu(int funct3, int funct7, uint32_t rs1, uint32_t rs2) {
  switch (funct3) {
    case 0: // StoreCodebook Instruction
          clusters = rs2;     
          return clusters; 
    case 1: // Weights Instruction
        if(funct7 & 0b100) {
            
            weights = (uint64_t) rs2 << 32 | rs1; 
            return weights;
        }
        return 0;
    case 2: // Mac instruction
        switch(funct7) {
            case 0b1000: // reset accumulator
                acc = 0;
                break;
            case 0b10000: // accumulate with weights 0-7
                acc = acc + multiply_add(rs1, rs2, clusters, extract_weight_set(weights, 0));
                break;
            case 0b10001: // accumulate with weights 8-15
                acc = acc + multiply_add(rs1, rs2, clusters, extract_weight_set(weights, 1));
                break;
            case 0b10010: // accumulate with weights 16-23
                acc = acc + multiply_add(rs1, rs2, clusters, extract_weight_set(weights, 2));
                break;
            case 0b10011: // accumulate with weights 24-31
                acc = acc + multiply_add(rs1, rs2, clusters, extract_weight_set(weights, 3));
                break;
                
            default:
                return acc;
        }
        return acc;
    
    default:
        break;

  }
  return 0;

}