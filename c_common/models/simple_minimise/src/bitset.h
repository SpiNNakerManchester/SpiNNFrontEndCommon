#include <stdbool.h>
#include <stdint.h>
#include "platform.h"

#ifndef __BITSET_H__

typedef struct _bitset_t
{
  unsigned int count;       // Keep track of members
  unsigned int n_words;     // Number of words in _data
  unsigned int n_elements;  // Number of elements which may be in the set
  uint32_t *_data;          // Pointer to data
} bitset_t;


// Empty a bitset entirely
static inline bool bitset_clear(bitset_t* b)
{
  // Clear the data
  for (unsigned int i = 0; i < b->n_words; i++)
  {
    b->_data[i] = 0x0;
  }

  // Reset the count
  b->count = 0;

  return true;
}


// Create a new bitset
static inline bool bitset_init(bitset_t* b, unsigned int length)
{
  // Malloc space for the data
  unsigned int n_words = length / 32;
  if (length % 32)
  {
    n_words++;
  }

  uint32_t* data = (uint32_t*) MALLOC(n_words * sizeof(uint32_t));
  if (data == NULL)
  {
    return false;
  }
  else
  {
    b->_data = data;
    b->n_words = n_words;
    b->n_elements = length;
    bitset_clear(b);
    return true;
  }
}


// Destruct a bitset
static inline void bitset_delete(bitset_t* b)
{
  FREE(b->_data);  // Free the storage
  b->_data = NULL;
  b->n_elements = 0;
}


// Add an element to a bitset
static inline bool bitset_add(bitset_t* b, unsigned int i)
{
  if (b->n_elements <= i)
  {
    return false;
  }

  // Determine the word and bit
  unsigned int word = i / 32;
  unsigned int bit  = 1 << (i & 31);

  b->_data[word] |= bit;  // Set the word and bit
  b->count++;             // Increment the count of set elements
  return true;
}


// Test if an element is in a bitset
static inline bool bitset_contains(bitset_t* b, unsigned int i)
{
  if (b->n_elements <= i)
  {
    return false;
  }

  // Determine the word and bit
  unsigned int word = i / 32;
  uint32_t bit  = 1 << (i & 31);
  return (bool) (b->_data[word] & bit);
}


// Remove an element from a bitset
static inline bool bitset_remove(bitset_t* b, unsigned int i)
{
  if (bitset_contains(b, i))
  {
    // Determine the word and bit
    unsigned int word = i >> 5;
    unsigned int bit  = 1 << (i & 0x1f);

    b->count--;              // Decrement the count of set elements
    b->_data[word] &= ~bit;  // Unset the bit of the appropriate word
    return true;
  }
  else
  {
    return false;
  }
}

#define __BITSET_H__
#endif  // __BITSET_H__
