/*
 * Copyright (c) 2019-2020 The University of Manchester
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#ifndef __M_TRIE_H__
#define __M_TRIE_H__

#include <malloc_extras.h>
#include "../common/routing_table.h"
#include "bit_set.h"
#include <stdbool.h>
#include <stdint.h>

// ---------------------------------------------------------------------

//! \brief constant initial source value
#define INIT_SOURCE 0x0

//! \brief the top bit of a word
#define TOP_BIT (1 << 31)

//! \brief Short routing table entry resulting from an m-trie
typedef struct m_trie_entry_t {
    // key_mask of the entry
    key_mask_t key_mask;

    // Sources of packets in the entry
    uint32_t source;
} m_trie_entry_t;

// \brief m-Trie structure
typedef struct m_trie_t {

    // Our parent
    struct _m_trie_node_t *parent;

    // Bit represented by this Node
    uint32_t bit;

    // Children of this Node
    struct m_trie_t *child_0;
    struct m_trie_t *child_1;
    struct m_trie_t *child_X;

    // Source(s) of packets which "reach" this node
    uint32_t source;
} m_trie_t;

//\brief Sub table structure used to hold partially-minimised routing tables
typedef struct sub_table_t {

    // Number of entries in the sub table
    unsigned int n_entries;

    // Route of all entries in the sub table
    uint32_t route;

    // Entries in the sub table
    m_trie_entry_t *entries;

    // Next sub table in the chain
    struct sub_table *next;
} sub_table_t;

// ---------------------------------------------------------------------

//! \brief Create a new (empty) node
//! \param[in] parent: the tree to add new node in
//! \param[in] bit: the bit to put in the new node
//! \return new tree
static inline m_trie_t *m_trie_new_node(m_trie_t *parent, uint32_t bit) {
    // Malloc room for the new m-Trie, then set the bit to be the MSB and
    // ensure the children are NULL.
    m_trie_t *node = MALLOC(sizeof(m_trie_t));

    node->parent = parent;
    node->bit = bit;
    node->child_0 = node->child_1 = node->child_X = NULL;
    node->source = INIT_SOURCE;

    return node;
}

//! \brief Create a new (empty) tree
//! return new tree.
static inline m_trie_t *m_trie_new(void) {
    return m_trie_new_node(NULL, TOP_BIT);
}

//! \brief Delete an existing tree
//! \param[in] node to delete from tree
static void m_trie_delete(m_trie_t *node) {
    if (node != NULL) {
        // Free any children
        m_trie_delete(node->child_0);
        m_trie_delete(node->child_1);
        m_trie_delete(node->child_X);

        // Free ourselves
        FREE(node);
    }
}

//! \brief Count the number of paths travelling through a node
//! \param[in] the free to count
//! \return the number of nodes in the tree
static unsigned int m_trie_count(m_trie_t *node) {
    if (node == NULL) {
        return 0;  // Not a node, so return 0
    } else if (!node->bit) {
        return 1;  // Node is a leaf, so return a 1
    }

    // Get the contribution from each child (if there are any)
    return m_trie_count(node->child_0) +
            m_trie_count(node->child_1) +
            m_trie_count(node->child_X);
}

//! \brief Extract routing table entries from a trie
//! \param[in] node: point in tree to search
//! \param[in] table: the table pointer to fill
//! \param[in] p_key: the key to find
//! \param[in] p_mask: the mask to find
//! \return a tree entry
static m_trie_entry_t *_get_entries(
        m_trie_t *node, m_trie_entry_t *table, uint32_t p_key,
        uint32_t p_mask) {
    if (node == NULL) {
        // Do nothing as this isn't a valid node.
    } else if (!node->bit) {
        // If this is a leaf then add an entry to the table representing this
        // entry and return a pointer to the next entry in the table.
        table->key_mask.key = p_key;
        table->key_mask.mask = p_mask;
        table->source = node->source;

        // Point to the next table entry
        table++;
    } else {
        // If this is not a leaf then get entries from any children we may have.
        uint32_t b = node->bit;  // Bit to set
        table = _get_entries(node->child_0, table, p_key, p_mask | b);
        table = _get_entries(node->child_1, table, p_key | b, p_mask | b);
        table = _get_entries(node->child_X, table, p_key, p_mask);
    }

    return table;
}

//! \brief get root entries
//! \param[in] node: top node
//! \param[in] table: the table pointer to store
static inline void m_trie_get_entries(m_trie_t *node, m_trie_entry_t *table) {
    _get_entries(node, table, INIT_SOURCE, INIT_SOURCE);
}

//! \brief Get the relevant child with which to follow a path
//! \param[in] node: tree to get child from
//! \param[in] key: key to find
//! \param[in] mask: mask to find
//return tree.
static inline m_trie_t **get_child(
        m_trie_t *node, uint32_t key, uint32_t mask) {
    if (mask & node->bit) {     // Either a 0 or a 1
        if (!(key & node->bit)) { // A 0 at this bit
            return &node->child_0;
        } else {                // A 1 at this bit
            return &node->child_1;
        }
    } else if (!(key & node->bit)) { // An X at this bit
        return &node->child_X;
    } else {
        return NULL;  // A `!' at this bit, abort
    }
}

//! \brief Traverse a path through the tree, adding elements as necessary
//! \param[in] node: the tree point to traverse
//! \param[in] key: the key to find
//! \param[in] mask: the mask to find
//! \param[in] source: the source to find
//! \return node with .....
static m_trie_t* m_trie_traverse(
        m_trie_t *node, uint32_t key, uint32_t mask, uint32_t source) {
    while (node->bit) {
        // See where to turn at this node
        m_trie_t **child = get_child(node, key, mask);

        // If no child was returned then the given key and mask were invalid
        if (!child) {
            return NULL;
        }

        // If the child is NULL then create a new child
        if (!*child) {
            *child = m_trie_new_node(node, node->bit >> 1);
        }

        // Delegate the traversal to the child
        node = *child;
    }

    // If we are a leaf then update our source and return our parent
    node->source |= source;
    return node->parent;
}

//! \brief Check if a path exists in a sub-trie
//! \param[in] node: the node to search
//! \param[in] key: the key to find
//! \param[in] mask: the mask to find
//! \return bool saying true if there is a path, false otherwise
static inline bool path_exists(m_trie_t *node, uint32_t key, uint32_t mask) {
    while (node->bit) {
        // See where to turn at this node
        m_trie_t **child = get_child(node, key, mask);

        // If there is no child then the path does not exist or the given path
        // was invalid.
        if (!child || !*child) {
            return false;
        }

        // Delegate the traversal to the child
        node = *child;
    }

    // If we are a leaf then the path must exist
    return true;
}

//! \brief ????
//! \param[in] node: ?
//! \param[in] key: ?
//! \param[in] mask: ?
//! \return ????
static bool m_trie_un_traverse(
        m_trie_t *node, uint32_t key, uint32_t mask) {
    if (!node->bit) {
        // If a leaf then free ourselves and then return to true to indicate
        // that this has occurred.
        FREE(node);
        return true;
    }

    // Get the child to attempt to un traverse
    m_trie_t **child = get_child(node, key, mask);

    if (m_trie_un_traverse(*child, key, mask)) {
        // The child has been freed, so remove our reference to it
        *child = NULL;
    }

    // If we have no children left then free ourselves and return true;
    // otherwise return false.
    if (node->child_0 == NULL && node->child_1 == NULL &&
            node->child_X == NULL) {
        FREE(node);
        return true;
    } else{
        return false;
    }
}

//! \brief get the source of a child
//! \param[in] node: the node to search
//! \param[in] key: the key to find
//! \param[in] mask: the mask to find
//! \return the source of the child.
static inline uint32_t get_source_from_child(
        m_trie_t *node, uint32_t key, uint32_t mask) {
    while (node->bit) {
        // See where to turn at this node
        m_trie_t **child = get_child(node, key, mask);

        // If there is no child then the path does not exist or the given path
        // was invalid.
        if (!child || !*child) {
            return false;
        }

        // Delegate the traversal to the child
        node = *child;
    }

    // If we are a leaf then return the source
    return node->source;
}

//! \brief adds a source to a child node
//! \param[in] node: node to search
//! \param[in] key: the key to search for
//! \param[in] mask: the mask to search for
//! \param[in] source: the source to add
static inline void add_source_to_child(
        m_trie_t *node, uint32_t key, uint32_t mask, uint32_t source) {
    while (node->bit) {
        // See where to turn at this node
        m_trie_t **child = get_child(node, key, mask);

        // If there is no child then the path does not exist or the given path
        // was invalid.
        if (!child || !*child) {
            return;
        }

        // Delegate the traversal to the child
        node = *child;
    }

    // If we are a leaf then modify the source
    node->source |= source;
}

//! \brief ????????
//! \param[in] child: ?
//! \param[in] key: ?
//! \param[in] mask: ?
static inline void un_traverse_in_child(
        m_trie_t **child, uint32_t key, uint32_t mask) {
    if (m_trie_un_traverse(*child, key, mask)) {
        *child = NULL;
    }
}

//! \brief Insert a new entry into the trie
//! \param[in] root the root to add the entry
//! \param[in] key the key to add to the entry
//! \param[in] mask the mask to add to the entry
//! \param[in] source the source to add to the entry
static inline void m_trie_insert(
        m_trie_t *root, uint32_t key, uint32_t mask, uint32_t source) {
    // Traverse a path through the trie and keep a reference to the leaf we
    // reach
    m_trie_t *leaf = m_trie_traverse(root, key, mask, source);

    // Attempt to find overlapping paths, going up the tree
    for (; leaf != NULL; leaf = leaf->parent) {
        m_trie_t **child_0 = &leaf->child_0;
        m_trie_t **child_1 = &leaf->child_1;
        m_trie_t **child_X = &leaf->child_X;

        if (*child_0 != NULL && path_exists(*child_0, key, mask) &&
                *child_1 != NULL && path_exists(*child_1, key, mask)) {
            // Get the combined sources from the existing children
            source = get_source_from_child(*child_0, key, mask) |
                     get_source_from_child(*child_1, key, mask);

            // Traverse the path in X and then un traverse in 0 and 1
            if (*child_X == NULL) {
                *child_X = m_trie_new_node(leaf, leaf->bit >> 1);
            }
            m_trie_traverse(*child_X, key, mask, source);

            // Un traverse in `0' and `1'
            un_traverse_in_child(child_0, key, mask);
            un_traverse_in_child(child_1, key, mask);

            // Update the key and mask
            key &= ~leaf->bit;
            mask &= ~leaf->bit;
        } else if (*child_X != NULL && path_exists(*child_X, key, mask) &&
                 *child_0 != NULL && path_exists(*child_0, key, mask)) {
            // Get the source for packets matching the `0'
            source = get_source_from_child(*child_0, key, mask);

            // Un traverse in `0'
            un_traverse_in_child(child_0, key, mask);

            // Add the sources to X
            add_source_to_child(*child_X, key, mask, source);

            // Update the key and mask
            key &= ~leaf->bit;
            mask &= ~leaf->bit;
        } else if (*child_X != NULL && path_exists(*child_X, key, mask) &&
                 *child_1 != NULL && path_exists(*child_1, key, mask)) {
            // Get the source for packets matching the `1'
            source = get_source_from_child(*child_1, key, mask);

            // Un traverse in `1'
            un_traverse_in_child(child_1, key, mask);

            // Add the sources to X
            add_source_to_child(*child_X, key, mask, source);

            // Update the key and mask
            key &= ~leaf->bit;
            mask &= ~leaf->bit;
        }
    }
}

//! \brief Create a new sub table, possibly appending to an existing list of
//! sub tables
//! \param[in] sb: create new sub table
//! \param[in] size: size of sub table
//! \param[in] route: the route
//! \return the new table
static inline sub_table_t* sub_table_new(
        sub_table_t **sb, unsigned int size, uint32_t route) {
    while (*sb != NULL) {
        sb = &((*sb)->next);
    }

    // Create a new sub table of the desired size
    *sb = MALLOC(sizeof(sub_table_t));
    (*sb)->entries = MALLOC(sizeof(m_trie_entry_t) * size);
    (*sb)->n_entries = size;
    (*sb)->route = route;
    (*sb)->next = NULL;

    return *sb;
}

//! \brief Expand a sub table into an existing routing table
//! \param[in] sb: table to expand
//! \param[in] table: table to expand into
static inline void sub_table_expand(sub_table_t *sb, table_t *table) {
    // Keep a count of the new number of entries
    table->size = 0;

    // For each sub table copy in the new entries
    entry_t *next = table->entries;
    for (; sb != NULL; sb = sb->next) {
        // Expand the current sub table
        for (unsigned int i = 0; i < sb->n_entries; i++) {
            next->key_mask.key = sb->entries[i].key_mask.key;
            next->key_mask.mask = sb->entries[i].key_mask.mask;
            next->source = sb->entries[i].source;
            next->route = sb->route;

            next++;
        }

        // Increase the size of the output table
        table->size += sb->n_entries;
    }
}

//! \brief Delete a set of sub tables
//! \param[in] sb: set of tables to delete
static void sub_table_delete(sub_table_t *sb) {
    // Delete local entries
    FREE(sb->entries);
    sb->entries = NULL;
    sb->n_entries = 0;

    // Recurse
    if (sb->next != NULL) {
        sub_table_delete(sb->next);
        sb->next = NULL;
    }

    // Delete ourselves
    FREE(sb);
}

//! \brief Use m-Tries to minimise a routing table
//! \param[in] table: the table to minimise
static inline void m_trie_minimise(table_t *table) {
    // For each set of unique routes in the table we construct an m-Trie to
    // minimise the entries; we then write the minimised table back in on-top
    // of the original table.

    // Keep a reference to entries we've already dealt with
    bit_set_t visited;
    bit_set_init(&visited, table->size);

    // Maintain a chain of partially minimised tables
    sub_table_t *sub_tables = NULL;

    // For every entry in the table that hasn't been inspected create a new
    // m-Trie, then add to it every entry with an equivalent route.
    for (unsigned int i = 0; i < table->size; i++) {
        if (bit_set_contains(&visited, i)) {
            continue;
        }

        // Create a new m-Trie
        m_trie_t *trie = m_trie_new();
        uint32_t route = table->entries[i].route;

        // Add all equivalent entries to the trie
        for (unsigned int j = i; j < table->size; j++) {
            if (table->entries[j].route == route) {
                // Mark the entry as visited
                bit_set_add(&visited, j);

                // Add to the trie
                uint32_t key = table->entries[j].key_mask.key;
                uint32_t mask = table->entries[j].key_mask.mask;
                uint32_t source = table->entries[j].source;
                m_trie_insert(trie, key, mask, source);
            }
        }

        // Read out all the minimised entries into a new sub table
        sub_table_t *sb = sub_table_new(&sub_tables, m_trie_count(trie), route);
        m_trie_get_entries(trie, sb->entries);

        // Delete the m-Trie
        m_trie_delete(trie);
    }

    // Overwrite the original routing table by copying entries back from the
    // sub_tables.
    sub_table_expand(sub_tables, table);

    // Clear up the sub_tables and bit_set.
    sub_table_delete(sub_tables); sub_tables = NULL;
    bit_set_delete(&visited);
}

#endif // __M_TRIE_H__
