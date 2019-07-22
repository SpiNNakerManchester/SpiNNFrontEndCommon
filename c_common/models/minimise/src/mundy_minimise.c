#include "spin1_api.h"
#include "ordered_covering.h"
#include "remove_default_routes.h"
#include "minimise.h"

//! \brief Method used to sort routing table entries.
//! \param[in] va: ?????
//! \param[in] vb: ??????
//! \return ???????
int compare_rte(const void *va, const void *vb) {
    // Grab the keys and masks
    keymask_t a = ((entry_t *) va)->keymask;
    keymask_t b = ((entry_t *) vb)->keymask;

    // Perform the comparison
    return ((int) keymask_count_xs(a)) - ((int) keymask_count_xs(b));
}

void minimise(table_t *table, uint32_t target_length){
    log_info("do qsort by route");
    //qsort(table->entries, table->size, sizeof(entry_t), compare_rte);

    // Perform the minimisation
    aliases_t aliases = aliases_init();
    log_debug("minimise");
    oc_minimise(table, target_length, &aliases);
    log_debug("done minimise");

    // Clean up the memory used by the aliases table
    log_debug("clear up aliases");
    aliases_clear(&aliases);
}
//! \brief the main entrance.
void c_main(void) {
    log_info("%u bytes of free DTCM", sark_heap_max(sark.heap, 0));

    // kick-start the process
    spin1_schedule_callback(compress_start, 0, 0, 3);

    // go
    spin1_start(SYNC_NOWAIT);	//##
}

