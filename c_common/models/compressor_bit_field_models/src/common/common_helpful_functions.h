#ifndef __COMMON_HELPFUL_FUNCTIONS_H__
#define __COMMON_HELPFUL_FUNCTIONS_H__

#include <debug.h>

//! \brief This function prints out an individual word of a bit_field,
// as a sequence of ones and zeros.
//! \param[in] e The word of a bit_field to be printed.
static inline void print_bit_field_entry_v2(uint32_t e, int offset) {
    counter_t i = 32;

    for ( ; i > 0; i--) {
        log_info("%d,%c", offset + i, ((e & 0x1) == 0) ? ' ' : '1');
        e >>= 1;
    }
}

//! \brief This function prints out an entire bit_field,
// as a sequence of ones and zeros.
//! \param[in] b The sequence of words representing a bit_field.
//! \param[in] s The size of the bit_field.
void print_bit_field_bits_v2(bit_field_t b, size_t s) {
    use(b);
    use(s);
    int i; //!< For indexing through the bit field

    for (i = s; i > 0; i--) {
	    print_bit_field_entry_v2(b[i], ((i - 1) * 32));
    }
}

#endif  // __COMMON_HELPFUL_FUNCTIONS_H__