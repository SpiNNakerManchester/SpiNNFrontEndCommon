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

#ifndef __ALIASES_H__
#define __ALIASES_H__

/* Aliases are built using a trie structure as this avoids the need for
 * rebalancing at the cost of more memory.
 */

#include <malloc_extras.h>
#include "../common/routing_table.h"
#include <debug.h>

/*****************************************************************************/
/* Vector-like object ********************************************************/

typedef struct _alias_element_t {  // Element of an alias list
    // key_mask of the element
    key_mask_t key_mask;

    // Source of packets matching the element
    uint32_t source;
} alias_element_t;

// Linked list of arrays
typedef struct _alias_list_t {
    // Elements in this instance
    unsigned int n_elements;
    // Max number of elements in this instance
    unsigned int max_size;
    // Next element in list of lists
    struct _alias_list_t *next;
    // Data region
    alias_element_t data;
} alias_list_t;

//! \brief Create a new list on the stack
//! \param[in] max_size: max size of memory to allocate to new list
//! \return new alias list. or NULL if not allocated
static alias_list_t* alias_list_new(unsigned int max_size) {
    // Compute how much memory to allocate
    unsigned int size =
            sizeof(alias_list_t) + (max_size - 1) * sizeof(alias_element_t);

    // Allocate and then fill in values
    alias_list_t *as = MALLOC(size);
    if (as == NULL){
        return NULL;
    }

    as->n_elements = 0;
    as->max_size = max_size;
    as->next = NULL;
    return as;
}

//! \brief Append an element to a list
//! \param[in] as: the alias list to append to
//! \param[in] val: the key mask to append to the alias
//! \param[in] source: the source to append to the alias
//! \return bool saying if it successfully appended or not
static bool alias_list_append(
        alias_list_t *as, key_mask_t val, uint32_t source) {
    if (as->n_elements < as->max_size) {
        (&as->data)[as->n_elements].key_mask = val;
        (&as->data)[as->n_elements].source = source;
        as->n_elements++;
        return true;
    }
    // Cannot append!
    return false;
}

//! \brief Get an element from the list
//! \param[in] as: the alias to locate a element from
//! \param[in] i: the index to get
//! \return the alias element for the i
static alias_element_t alias_list_get(alias_list_t *as, unsigned int i) {
    return (&as->data)[i];
}

//! \brief Append a list to an existing list
//! \param[in] a: alias list to append to
//! \param[in] b:al;ias list to append
static void alias_list_join(alias_list_t *a, alias_list_t *b) {
    // Traverse the list elements until we reach the end.
    while (a->next != NULL) {
        a = a->next;
    }

    // Store the next element
    a->next = b;
}

//! \brief Delete all elements in an alias list
//! \param[in] a: alias list to delete.
void alias_list_delete(alias_list_t *a) {
    if (a->next != NULL) {
        alias_list_delete(a->next);
        a->next = NULL;
    }
    FREE(a);
}

/*****************************************************************************/


/*****************************************************************************/
/* Map-like object ***********************************************************/
// Implemented as an AA tree

//! \brief the key union from a key and mask to a 64 bit number
typedef union a_key_t {
    // key mast combo
    key_mask_t km;

    // the 64 bit int version
    int64_t as_int;
} a_key_t;

// node struct
typedef struct node_t {
    // Key and value of this node
    a_key_t key;

    // alias ......
    alias_list_t *val;

    // tree level maybe?
    unsigned int level;

    // left child
    struct node_t *left;

    // right child
    struct node_t *right;
} node_t;

//! \brief top of tree
typedef struct aliases_t {
    node_t *root;
} aliases_t;

//! \brief Create a new, empty, aliases container
//! return new alias list
static aliases_t aliases_init(void) {
    aliases_t aliases = {NULL};
    return aliases;
}

//! \brief ????????
//! \param[in] node: ????????
//! \param[in] key: ????????
//! \return ???????????
static node_t *_aliases_find_node(node_t *node, a_key_t key) {
    while (node != NULL) {
        if (key.as_int == node->key.as_int) {
            // This is the requested item, return it
            return node;
        }

        if (key.as_int < node->key.as_int) {
            // Go left
            node = node->left;
        } else {
            // Go right
            node = node->right;
        }
    }
    return NULL;  // We didn't find the requested item
}


//! \brief Retrieve an element from an aliases container
//! \param[in] a: ??????????
//! \param[in] key: ????????????
//! \return ?????????????
static alias_list_t *aliases_find(aliases_t *a, key_mask_t key) {
    // Search the tree
    node_t *node = _aliases_find_node(a->root, (a_key_t) key);
    if (node == NULL) {
        return NULL;
    }
    return node->val;
}


//! \brief See if the aliases contain holds an element
//! \param[in] a: alias
//! \param[in] key: the key mask struct
//! \return bool saying if the alias has the key mask.
static bool aliases_contains(aliases_t *a, key_mask_t key) {
    return aliases_find(a, key) != NULL;
}

//! \brief ???????
//! \param[in] n: ??????????
//! \return ??????????
static node_t *_aliases_skew(node_t *n) {
    if (n == NULL) {
        return NULL;
    }
    if (n->left == NULL || n->level != n->left->level) {
        return n;
    }

    node_t *node_pointer = n->left;
    n->left = node_pointer->right;
    node_pointer->right = n;
    return node_pointer;
}

//! \brief ??????????
//! \param[in] n: ??????????
//! \return ??????????
static node_t *_aliases_split(node_t *n) {
    if (n == NULL) {
        return NULL;
    }
    if (n->right == NULL || n->right->right == NULL
            || n->level != n->right->right->level) {
        return n;
    }

    node_t *r = n->right;
    n->right = r->left;
    r->left = n;
    r->level++;
    return r;
}

//! \brief ??????????
//! \param[in] n: ??????????
//! \param[in] key: ????????
//! \param[in] val: ?????????
//! \return bool stating if the insert was successful or not
static bool _aliases_insert(
        node_t *n, a_key_t key, alias_list_t *val) {

    if (n == NULL) {
        // If the node is NULL then create a new Node
        // Malloc room for the node
        n = MALLOC(sizeof(node_t));
        if (n == NULL){
            log_error("failed to allocate memory for node");
            return false;
        }

        // Assign the values
        n->key = key;
        n->val = val;
        n->left = n->right = NULL;
        n->level = 1;

        return true;
    }

    if (key.as_int < n->key.as_int) {
        // Go left
        bool success = _aliases_insert(n->left, key, val);
        if (!success){
            return false;
        }
    } else if (key.as_int > n->key.as_int) {
        // Go right
        bool success = _aliases_insert(n->right, key, val);
        if (!success){
            return false;
        }
    } else {
        // Replace the value
        n->val = val;
    }

    // Rebalance the tree
    n = _aliases_skew(n);
    n = _aliases_split(n);

    return true;
}


//! \brief Add/overwrite an element into an aliases tree
//! \param[in] a: ??????????
//! \param[in] key: key mask struct
//! \param[in] value: ????????
//! \return bool stating if the insert was successful or not
static bool aliases_insert(
        aliases_t *a, key_mask_t key, alias_list_t *value) {
    // Insert into, and balance, the tree

   return _aliases_insert(a->root, (a_key_t) key, value);
}


//! \brief Remove an element from an aliases tree
//! \param[in] a: aliases
//! \param[in] key: the key mask struct
static inline void aliases_remove(aliases_t *a, key_mask_t key) {
    // XXX This is a hack which removes the reference to the element in the
    // tree but doesn't remove the Node from the tree.
    node_t *n = _aliases_find_node(a->root, (a_key_t) key);
    if (n != NULL) {
        n->val = NULL;
    }
}

//! \brief clears a node from the aliase tree
//! \param[in] n: the note to clear from the alias tree
static void _aliases_clear(node_t *n) {
    if (n == NULL) {
        return;
    }

    // Remove any children
    if (n->left != NULL) {
        _aliases_clear(n->left);
    }
    if (n->right != NULL) {
        _aliases_clear(n->right);
    }

    // Clear the value
    if (n->val != NULL) {
        alias_list_delete(n->val);
    }

    // Remove self
    FREE(n);
}


//! \brief Remove all elements from an aliases container and free all
//! sub-containers
//! \param[in] a: the aliases tree.
static void aliases_clear(aliases_t *a) {
    _aliases_clear(a->root);
}

/*****************************************************************************/

#endif  // __ALIASES_H__
