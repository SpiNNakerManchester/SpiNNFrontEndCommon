/*
 * Copyright (c) 2019 The University of Manchester
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

//! \file
//! \brief An ordered covering of routing table entries
#ifndef __ORDERED_COVERING_H__
#define __ORDERED_COVERING_H__

#include <malloc_extras.h>
#include <debug.h>
#include "aliases.h"
#include "bit_set.h"
#include "merge.h"
#include "../common/routing_table.h"

//! \brief State of the ordered covering
typedef struct _sets_t {
    bit_set_t *best;    //!< The best covering found so far
    bit_set_t *working; //!< The covering currently being worked on
} __sets_t;

//! \brief Get the index where the routing table entry resulting from a merge
//!     should be inserted.
//! \param[in] generality: The number of least-significant bits masked out
//! \return The insertion point for this generality factor
static unsigned int oc_get_insertion_point(
        const unsigned int generality) {
    // Perform a binary search of the table to find entries of generality - 1
    const unsigned int g_m_1 = generality - 1;
    int bottom = 0;
    int top = routing_table_get_n_entries();
    int pos = top / 2;

    // get first entry
    entry_t* entry = routing_table_get_entry(pos);
    unsigned int count_xs = key_mask_count_xs(entry->key_mask);

    // iterate till found something
    while ((bottom < pos) && (pos < top) && (count_xs != g_m_1)) {
        if (count_xs < g_m_1) {
            bottom = pos;
        } else {
            top = pos;
        }

        // Update the position
        pos = bottom + (top - bottom) / 2;

        // update entry and count
        entry = routing_table_get_entry(pos);
        count_xs = key_mask_count_xs(entry->key_mask);
    }

    // Iterate through the table until either the next generality or the end of
    // the table is found.
    while (pos < routing_table_get_n_entries() &&
            (count_xs < generality)) {
        pos++;
        if (pos < routing_table_get_n_entries()) {
            entry = routing_table_get_entry(pos);
            count_xs = key_mask_count_xs(entry->key_mask);
        } else {
            // FIX MUNDY LOOKING PAST END OF TABLE!
            count_xs = 0;
        }
    }

    return pos;
}


//! \brief Remove from a merge any entries which would be covered by being
//!     existing entries if they were included in the given merge.
//! \param[in] merge: The merge to consider
//! \param[in] min_goodness:
//!     Minimum goodness factor for a merge to be performed
//! \param[in] stop_compressing: Whether the compressor should stop;
//!     points to a variable _set by interrupt_
//! \param[out] changed: Whether the merge drops below goodness level
//! \return Whether the method was successful in completing or not
static inline bool oc_up_check(
        merge_t *merge, int min_goodness,
        volatile bool *stop_compressing, bool *changed) {
    min_goodness = (min_goodness > 0) ? min_goodness : 0;

    // Get the point where the merge will be inserted into the table.
    unsigned int generality = key_mask_count_xs(merge->key_mask);
    unsigned int insertion_index = oc_get_insertion_point(generality);

    // For every entry in the merge check that the entry would not be covered by
    // any existing entries if it were to be merged.

    for (unsigned int _i = routing_table_get_n_entries(),
            i = routing_table_get_n_entries() - 1;
            (_i > 0) && (merge_goodness(merge) > min_goodness);
            _i--, i--) {
        // safety check for timing limits
        if (*stop_compressing) {
            return false;
        }

        if (!merge_contains(merge, i)) {
            // If this entry is not contained within the merge skip it
            continue;
        }

        // Get the key_mask for this entry
        key_mask_t km = routing_table_get_entry(i)->key_mask;

        // Otherwise look through the table from the insertion point to the
        // current entry position to ensure that nothing covers the merge.
        for (unsigned int j = i + 1; j < insertion_index; j++) {
            key_mask_t other_km = routing_table_get_entry(j)->key_mask;

            // If the key masks intersect then remove this entry from the merge
            // and recalculate the insertion index.
            if (key_mask_intersect(km, other_km)) {
                // Indicate the the merge has changed
                *changed = true;

                // Remove from the merge
                merge_remove(merge, i);
                generality = key_mask_count_xs(merge->key_mask);
                insertion_index = oc_get_insertion_point(generality);
            }
        }
    }

    // Completely empty the merge if its goodness drops below the minimum
    // specified
    if (merge_goodness(merge) <= min_goodness) {
        *changed = true;
        merge_clear(merge);
    }

    return true;
}

//! \brief Compute what bits can be set and cleared in the covering mask
//! \param[in] merge_km: The merge being considered
//! \param[in] covered_km: The key-mask that the merge must cover
//! \param[in,out] stringency: Variable holding the number of masked out bits
//! \param[in,out] set_to_zero: Variable holding the bits to set to zero
//! \param[in,out] set_to_one: Variable holding the bits to set to one
static void _get_settable(
        key_mask_t merge_km, key_mask_t covered_km, unsigned int *stringency,
        uint32_t *set_to_zero, uint32_t *set_to_one) {
    // We can "set" any bit where the merge contains an X and the covered
    // entry doesn't.
    uint32_t setable = ~key_mask_get_xs(covered_km) & key_mask_get_xs(merge_km);
    unsigned int new_stringency = __builtin_popcount(setable);

    uint32_t this_set_to_zero = setable &  covered_km.key;
    uint32_t this_set_to_one  = setable & ~covered_km.key;

    // The stringency indicates how many bits *could* be set to avoid the cover.
    // If this new stringency is lower than the existing stringency then we
    // reset which bits may be set.
    if (new_stringency < *stringency) {
        // Update the stringency count
        *stringency  = new_stringency;
        *set_to_zero = this_set_to_zero;
        *set_to_one  = this_set_to_one;
    } else if (new_stringency == *stringency) {
        *set_to_zero |= this_set_to_zero;
        *set_to_one  |= this_set_to_one;
    }
}

//! \brief Get candidates for removal
//! \param[in] m: Merge from which entries will be removed
//! \param[in] settable: Mask of bits to set
//! \param[in] to_one: True if setting to one, otherwise false
//! \param[in] sets: The bitfields describing what is being considered
//! \return The updated version of \p sets
static inline __sets_t _get_removables(
        merge_t *m, uint32_t settable, bool to_one, __sets_t sets) {
    // For each bit which we are trying to set while the best set doesn't
    // contain only one entry.
    for (uint32_t bit = (1 << 31); bit > 0 && sets.best->count != 1;
            bit >>= 1) {

        // If this bit cannot be set we ignore it
        if (!(bit & settable)) {
            continue;
        }

        // Loop through the table adding to the working set any entries with
        // either a X or a 0 or 1 (as specified by `to_one`) to the working set
        // of entries to remove.
        int entry = 0;
        for (int i = 0; i < routing_table_get_n_entries(); i++) {

            // Skip if this isn't an entry
            if (!merge_contains(m, i)) {
                continue;
            }

            // See if this entry should be removed
            key_mask_t km = routing_table_get_entry(i)->key_mask;

            // check entry has x or 1 or 0 in this position.
            if ((bit & ~km.mask) || (!to_one && (bit & km.key)) ||
                    (to_one && (bit & ~km.key))) {

                // NOTE: Indexing by position in merge!
                bit_set_add(sets.working, entry);
            }

            // Increment the index into the merge set
            entry++;
        }

        // If `working` contains fewer entries than `best` or `best` is empty
        // swap `working and best`. Otherwise just empty the working set.
        if (sets.best->count == 0 || sets.working->count < sets.best->count) {
            // Perform the swap
            bit_set_t *c = sets.best;
            sets.best = sets.working;
            sets.working = c;
        }

        // Clear the working merge
        bit_set_clear(sets.working);
    }

    return sets;
}


//! \brief Remove entries from a merge such that the merge would not cover
//!     existing entries positioned below the merge.
//! \param[in] merge: The merge to eventually apply
//! \param[in] min_goodness:
//!     The minimum number of bits to mask out for removal to be considered
//! \param[in] aliases: Describes what entries alias what other entries
//! \param[out] failed_by_malloc:
//!     Flag saying if it failed due to running out of memory
//! \param[in] stop_compressing:
//!     Variable saying whether the compressor should stop, _set by interrupt_
//! \return Whether it was successful or not
static bool oc_down_check(
        merge_t *merge, int min_goodness, aliases_t *aliases,
        bool *failed_by_malloc,
        volatile bool *stop_compressing) {
    min_goodness = (min_goodness > 0) ? min_goodness : 0;

    while (merge_goodness(merge) > min_goodness) {
        // safety check for timing limits
        if (*stop_compressing) {
            log_error("failed due to timing");
            return false;
        }

        // Record if there were any covered entries
        bool covered_entries = false;
        // Not at all stringent
        unsigned int stringency = 33;
        // Mask of which bits could be set to zero
        uint32_t set_to_zero = 0x0;
        // Mask of which bits could be set to one
        uint32_t set_to_one  = 0x0;

        // Look at every entry between the insertion index and the end of the
        // table to see if there are any entries which could be covered by the
        // entry resulting from the merge.
        int insertion_point =
                oc_get_insertion_point(key_mask_count_xs(merge->key_mask));

        for (int i = insertion_point;
                i < routing_table_get_n_entries() && stringency > 0;
                i++) {
            // safety check for timing limits
            if (*stop_compressing) {
                log_error("failed due to timing");
                return false;
            }

            key_mask_t km = routing_table_get_entry(i)->key_mask;
            if (key_mask_intersect(km, merge->key_mask)) {
                if (!aliases_contains(aliases, km)) {
                    // The entry doesn't contain any aliases so we need to
                    // avoid hitting the key that has just been identified.
                    covered_entries = true;
                    _get_settable(
                            merge->key_mask, km, &stringency, &set_to_zero,
                            &set_to_one);
                } else {
                    // We need to avoid any key_masks contained within the
                    // alias table.
                    alias_list_t *the_alias_list = aliases_find(aliases, km);
                    while (the_alias_list != NULL) {
                        // safety check for timing limits
                        if (*stop_compressing) {
                            log_error("failed due to timing");
                            return false;
                        }
                        for (unsigned int j = 0; j < the_alias_list->n_elements;
                                j++) {

                            // safety check for timing limits
                            if (*stop_compressing) {
                                log_error("failed due to timing");
                                return false;
                            }

                            km = alias_list_get(the_alias_list, j).key_mask;

                            if (key_mask_intersect(km, merge->key_mask)) {
                                covered_entries = true;
                                _get_settable(
                                        merge->key_mask, km, &stringency,
                                        &set_to_zero, &set_to_one);
                            }
                        }

                        // Progress through the alias list
                        the_alias_list = the_alias_list->next;
                    }
                }
            }
        }

        if (!covered_entries) {
            // If there were no covered entries then we needn't do anything
            return true;
        }

        if (stringency == 0) {
            // We can't avoid a covered entry at all so we need to empty the
            // merge entirely.
            merge_clear(merge);
            return true;
        }

        // Determine which entries could be removed from the merge and then
        // pick the smallest number of entries to remove.
        __sets_t sets;

        // allocate and free accordingly
        sets.best = MALLOC(sizeof(bit_set_t));
        if (sets.best == NULL) {
            log_error("failed to alloc sets.best");
            *failed_by_malloc = true;
            return false;
        }

        sets.working = MALLOC(sizeof(bit_set_t));
        if (sets.working == NULL) {
            log_error("failed to alloc sets.working");
            *failed_by_malloc = true;

            // free stuff already malloc
            bit_set_delete(sets.best);
            FREE(sets.best);
            return false;
        }

        bool success = bit_set_init(sets.best, merge->entries.count);
        if (!success) {
            log_error("failed to init the bitfield best");
            *failed_by_malloc = true;

            // free stuff already malloc
            bit_set_delete(sets.best);
            bit_set_delete(sets.working);
            FREE(sets.best);
            FREE(sets.working);
            return false;
        }

        success = bit_set_init(sets.working, merge->entries.count);
        if (!success) {
            log_error("failed to init the bitfield working.");
            *failed_by_malloc = true;

            // free stuff already malloc
            bit_set_delete(sets.best);
            bit_set_delete(sets.working);
            FREE(sets.best);
            FREE(sets.working);
            return false;
        }

        // Get the entries that can be removed because of the filtering we have
        // computed above
        sets = _get_removables(merge, set_to_zero, false, sets);
        sets = _get_removables(merge, set_to_one, true, sets);

        // Remove the specified entries
        int entry = 0;
        for (int i = 0; i <routing_table_get_n_entries(); i++) {
            // safety check for timing limits
            if (*stop_compressing) {
                log_error("failed due to timing");
                bit_set_delete(sets.best);
                bit_set_delete(sets.working);
                FREE(sets.best);
                FREE(sets.working);
                return false;
            }

            if (merge_contains(merge, i)) {
                if (bit_set_contains(sets.best, entry)) {
                    // Remove this entry from the merge
                    merge_remove(merge, i);
                }
                entry++;
            }
        }

        // Tidy up
        bit_set_delete(sets.best);
        FREE(sets.best);
        sets.best=NULL;
        bit_set_delete(sets.working);
        FREE(sets.working);
        sets.working=NULL;

        // If the merge only contains 1 entry empty it entirely
        if (merge->entries.count == 1) {
            log_debug("final merge clear");
            merge_clear(merge);
        }
    }
    log_debug("returning from down check");
    return true;
}


//! \brief Get the best merge which can be applied to a routing table
//! \param[in] aliases: Describes what entries alias what other entries
//! \param[in,out] best: The best merge found
//! \param[out] failed_by_malloc: Flag saying failed by memory exhaustion
//! \param[in] stop_compressing: Variable saying if compression should stop;
//!     _set by interrupt_
//! \return Whether successful or not.
static inline bool oc_get_best_merge(
        aliases_t *aliases, merge_t *best, bool *failed_by_malloc,
        volatile bool *stop_compressing) {
    // Keep track of which entries have been considered as part of merges.
    bit_set_t considered;
    bool success = bit_set_init(
            &considered, routing_table_get_n_entries());
    if (!success) {
        log_warning("failed to initialise the bit_set. throwing response malloc");
        *failed_by_malloc = true;
        return false;
    }

    // Keep track of the current best merge and also provide a working merge
    merge_t working;

    success = merge_init(best, routing_table_get_n_entries());
    if (!success) {
        log_warning("failed to init the merge best. throw response malloc");
        *failed_by_malloc = true;

        // free bits we already done
        bit_set_delete(&considered);

        // return false
        return false;
    }

    success = merge_init(&working, routing_table_get_n_entries());
    if (!success) {
        log_warning("failed to init the merge working. throw response malloc");
        *failed_by_malloc = true;

        // free bits we already done
        merge_delete(best);
        bit_set_delete(&considered);

        // return false
        return false;
    }

    // For every entry in the table see with which other entries it could be
    // merged.
    log_debug("starting search for merge entry");
    for (int i = 0; i < routing_table_get_n_entries(); i++) {
        // safety check for timing limits
        if (*stop_compressing) {
            log_info("closed due to stop request");
            // free bits we already done
            merge_delete(best);
            bit_set_delete(&considered);
            return false;
        }

        // If this entry has already been considered then skip to the next
        if (bit_set_contains(&considered, i)) {
            continue;
        }

        // Otherwise try to build a merge
        // Clear the working merge
        merge_clear(&working);

        // Add to the merge
        merge_add(&working, i);

        // Mark this entry as considered
        bit_set_add(&considered, i);

        // Get the entry
        entry_t *entry = routing_table_get_entry(i);

        // Try to merge with other entries
        log_debug("starting second search at index %d", i);
        for (int j = i+1; j < routing_table_get_n_entries(); j++) {
            // safety check for timing limits
            if (*stop_compressing) {
                log_info("closed due to stop request");
                // free bits we already done
                merge_delete(best);
                bit_set_delete(&considered);
                return false;
            }

            // Get the other entry
            entry_t *other = routing_table_get_entry(j);

            // check if merge-able
            if (entry->route == other->route) {
                // If the routes are the same then the entries may be merged
                // Add to the merge
                merge_add(&working, j);

                // Mark the other entry as considered
                bit_set_add(&considered, j);
            }
        }

        if (merge_goodness(&working) <= merge_goodness(best)) {
            continue;
        }

        // Perform the first down check
        success = oc_down_check(
                &working, merge_goodness(best), aliases, failed_by_malloc,
                stop_compressing);
        if (!success) {
            log_error("failed to down check.");

            // free bits we already done
            merge_delete(best);
            bit_set_delete(&considered);

            return false;
        }

        if (merge_goodness(&working) <= merge_goodness(best)) {
            continue;
        }

        // Perform the up check, seeing if this actually makes a change to the
        // size of the merge.
        bool changed = false;
        success = oc_up_check(
                &working, merge_goodness(best), stop_compressing, &changed);
        if (!success) {
            log_info("failed to upcheck");
            // free bits we already done
            merge_delete(best);
            bit_set_delete(&considered);
            return false;
        }

        // if changed the merge
        if (changed) {
            if (merge_goodness(&working) <= merge_goodness(best)) {
                continue;
            }

            // If the up check did make a change then the down check needs to
            // be run again.
            log_debug("down check");
            success = oc_down_check(
                    &working, merge_goodness(best), aliases, failed_by_malloc,
                    stop_compressing);
            if (!success) {
                log_error("failed to down check. ");

                // free bits we already done
                merge_delete(best);
                bit_set_delete(&considered);

                return false;
            }
        }

        // If the merge is still better than the current best merge we swap the
        // current and best merges to record the new best merge.
        if (merge_goodness(best) < merge_goodness(&working)) {
            merge_t other = working;
            working = *best;
            *best = other;
        }
    }

    // Tidy up
    merge_delete(&working);
    bit_set_delete(&considered);
    log_debug("n entries is %d", routing_table_get_n_entries());
    // found the best merge. return true
    return true;
}


//! \brief Apply a merge to the table against which it is defined
//! \param[in] merge: The merge to apply to the routing tables
//! \param[in] aliases: Describes what entries alias what other entries
//! \param[out] failed_by_malloc: Flag saying failed by memory exhaustion
//! \return Whether successful or not
static inline bool oc_merge_apply(
        merge_t *merge, aliases_t *aliases, bool *failed_by_malloc) {
    // Get the new entry
    entry_t new_entry;
    new_entry.key_mask = merge->key_mask;
    new_entry.route = merge->route;
    new_entry.source = merge->source;

    log_debug("new entry k %x mask %x route %x source %x x mergable is %d",
            new_entry.key_mask.key, new_entry.key_mask.mask, new_entry.route,
            new_entry.source, merge->entries.count);

    // Get the insertion point for the new entry
    int insertion_point =
            oc_get_insertion_point(key_mask_count_xs(merge->key_mask));
    log_debug("the insertion point is %d", insertion_point);

    // Keep track of the amount of reduction of the finished table
    int reduced_size = 0;

    // Create a new aliases list with sufficient space for the key_masks of all
    // of the entries in the merge. NOTE: IS THIS REALLY REQUIRED!?
    log_debug("new alias");
    alias_list_t *new_aliases = alias_list_new(merge->entries.count);
    if (new_aliases == NULL) {
        log_error("failed to malloc new alias list");
        *failed_by_malloc = true;
        return false;
    }

    log_debug("alias insert");
    bool malloc_success =
            aliases_insert(aliases, new_entry.key_mask, new_aliases);
    if (!malloc_success) {
        log_error("failed to malloc new alias list during insert");
        *failed_by_malloc = true;
        return false;
    }

    // Use two iterators to move through the table copying entries from one
    // position to the other as required.
    int insert = 0;

    log_debug("routing table entries = %d", routing_table_get_n_entries());

    for (int remove = 0; remove < routing_table_get_n_entries(); remove++) {
        // Grab the current entry before we possibly overwrite it
        entry_t* current = routing_table_get_entry(remove);
        log_debug("bacon");
        log_debug("entry %d being processed has key %x or %d, mask %x "
                "route %x source %x", remove, current->key_mask.key,
                current->key_mask.key, current->key_mask.mask, current->route,
                current->source);
        // Insert the new entry if this is the correct position at which to do
        // so
        if (remove == insertion_point) {
            log_debug("remove == insert at index %d and insert %d at "
                    "insert point", remove, insert);

            entry_t *insert_entry = routing_table_get_entry(insert);

            // move data between entries
            insert_entry->key_mask.key = new_entry.key_mask.key;
            insert_entry->key_mask.mask = new_entry.key_mask.mask;
            insert_entry->route = new_entry.route;
            insert_entry->source = new_entry.source;
            insert++;
        }

        // If this entry is not contained within the merge then copy it from its
        // current position to its new position.
        if (!merge_contains(merge, remove)) {
            log_debug("not contains at index %d and insert %d at insert point",
                    remove, insert);

            entry_t *insert_entry = routing_table_get_entry(insert);

            // move data between entries
            insert_entry->key_mask.key = current->key_mask.key;
            insert_entry->key_mask.mask = current->key_mask.mask;
            insert_entry->route = current->route;
            insert_entry->source = current->source;
            insert++;

        } else {
            log_debug("merge contains at index %d and insert %d at "
                    "insert point", remove, insert);

            // Otherwise update the aliases table to account for the entry
            // which is being merged.
            key_mask_t km = current->key_mask;
            uint32_t source = current->source;

            if (aliases_contains(aliases, km)) {
                // Join the old list of aliases with the new
                alias_list_join(new_aliases, aliases_find(aliases, km));

                // Remove the old aliases entry
                aliases_remove(aliases, km);
            } else {
                // Include the key_mask in the new list of aliases
                alias_list_append(new_aliases, km, source);
            }

            // Decrement the final table size to account for this entry being
            // removed.
            reduced_size++;

            log_debug("at index %d and insert %d not at merge point",
                    remove, insert);
        }
    }

    log_debug("alias delete");
    alias_list_delete(new_aliases);
    log_debug("alias delete end");

    // If inserting beyond the old end of the table then perform the insertion
    // at the new end of the table.
    if (insertion_point == routing_table_get_n_entries()) {
        log_debug("insert point was at end of table, new insert point is %d",
                insert);
        entry_t *insert_entry = routing_table_get_entry(insert);
        insert_entry->key_mask.key = new_entry.key_mask.key;
        insert_entry->key_mask.mask = new_entry.key_mask.mask;
        insert_entry->route = new_entry.route;
        insert_entry->source = new_entry.source;
    }

    // Record the new size of the table
    routing_table_remove_from_size(reduced_size - 1);
    return true;
}


//! \brief Apply the ordered covering algorithm to a routing table
//! \details Minimise the table until either the table is shorter than the
//!     target length or no more merges are possible.
//! \param[in] target_length: The length to reach
//! \param[out] failed_by_malloc: Flag stating that it failed due to malloc
//! \param[out] stop_compressing: Variable saying if the compressor should stop
//!    and return false; _set by interrupt_ DURING the run of this method!
//! \return Whether successful or not.
bool minimise_run(
        int target_length, bool *failed_by_malloc,
        volatile bool *stop_compressing) {
    // check if any compression actually needed
    log_debug("n entries before compression is %d",
            routing_table_get_n_entries());

    if (routing_table_get_n_entries() < target_length) {
        log_info("does not need compression.");
        return true;
    }

    // Some Mundy black magic
    aliases_t aliases = aliases_init();

    // start the merger process
    log_debug("n entries is %d", routing_table_get_n_entries());
    int attempts = 0;

    while ((routing_table_get_n_entries() > target_length) &&
            !*stop_compressing) {
        log_debug("n entries is %d", routing_table_get_n_entries());

        // Get the best possible merge, if this merge is empty then break out
        // of the loop.
        merge_t merge;
        bool success = oc_get_best_merge(
                &aliases, &merge, failed_by_malloc, stop_compressing);
        if (!success) {
            log_debug("failed to do get best merge. "
                    "the number of merge cycles were %d", attempts);
            aliases_clear(&aliases);
            return false;
        }

        log_debug("best merge end");
        unsigned int count = merge.entries.count;

        if (count > 1) {
            // Apply the merge to the table if it would result in merging
            // actually occurring.
            //routing_tables_print_out_table_sizes();
            log_debug("merge apply");
            bool malloc_success = oc_merge_apply(
                    &merge, &aliases, failed_by_malloc);

            if (!malloc_success) {
                log_error("failed to malloc");
                aliases_clear(&aliases);
                return false;
            }
            log_debug("merge apply end");
            //routing_tables_print_out_table_sizes();
        }

        // Free any memory used by the merge
        log_debug("merge delete");
        merge_delete(&merge);
        log_debug("merge delete end");

        // Break out of the loop if no merge could be performed (indicating
        // that no more minimisation is possible).
        if (count < 2) {
            break;
        }
        attempts += 1;
    }

    // shut down timer. as passed the compression
    spin1_pause();

    // if it failed due to timing, report and then reset and fail.
    if (*stop_compressing) {
        log_info("Asked to stop. reached %d entries over %d attempts",
                routing_table_get_n_entries(), attempts);
        spin1_pause();
        aliases_clear(&aliases);
        return false;
    }

    log_info("entries after compressed = %d, target_length = %d, stop = %d, "
            " the number of merge cycles were %d",
            routing_table_get_n_entries(), target_length, *stop_compressing,
            attempts);

    log_debug("compressed!!!");
    log_debug("produced table with %d entries", routing_table_get_n_entries());
    aliases_clear(&aliases);
    return true;
}

#endif  // __ORDERED_COVERING_H__
