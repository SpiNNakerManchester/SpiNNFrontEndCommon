#ifndef __FILTER_INFO_H__

//! \brief the elements in a filter info (bitfield wrapper)
typedef struct filter_info_t{
    // bit field master pop key
    uint32_t key;
    // n words representing the bitfield
    int n_words;
    // the words of the bitfield
    bit_field_t data;
} filter_info_t;

//! \brief the elements in the bitfield region
typedef struct filter_region_t{
    // how many filters there are
    uint32_t n_filters;
    // the filters
    filter_info_t filters[];
} filter_region_t;

#define __FILTER_INFO_H__
#endif  // __FILTER_INFO_H__
