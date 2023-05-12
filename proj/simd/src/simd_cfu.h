#include "cfu.h"

#ifndef _SIMD_CFU_H
#define _SIMD_CFU_H

#define cfu_storeCodebook(a) cfu_op0(0, 0, a)

#define cfu_storeWeights(a, b) cfu_op1(0b100, a, b)

#define cfu_reset() cfu_op2(0b1000, 0, 0)
#define cfu_accumulate_0(a, b) cfu_op2(0b10000, a, b)
#define cfu_accumulate_1(a, b) cfu_op2(0b10001, a, b)
#define cfu_accumulate_2(a, b) cfu_op2(0b10010, a, b)
#define cfu_accumulate_3(a, b) cfu_op2(0b10011, a, b)
#define cfu_read() cfu_op2(0, 0, 0)



#endif