#ifndef __KEY_ATOM_MAP_H__

//! \brief struct for key and atoms
typedef struct key_atom_pair_t{
    // key
    uint32_t key;
    // n atoms
    int n_atoms;
} key_atom_pair_t;

//! \brief key atom map struct
typedef struct key_atom_data_t{
    // how many key atom maps
    int n_pairs;
    // the list of maps
    key_atom_pair_t pairs[];
} key_atom_data_t;

#define __KEY_ATOM_MAP_H__
#endif  // __KEY_ATOM_MAP_H__