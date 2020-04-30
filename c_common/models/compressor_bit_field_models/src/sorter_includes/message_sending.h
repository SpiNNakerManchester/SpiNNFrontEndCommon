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

#ifndef __MESSAGE_SENDING_H__
#define __MESSAGE_SENDING_H__

#include <malloc_extras.h>
#include "../common/constants.h"

//! how many tables the uncompressed router table entries is
#define N_UNCOMPRESSED_TABLE 1

//! \brief sends the sdp message. assumes all params have already been set
//! \param[in] my_msg: sdp message to send
//! \param[in] processor_id: the processor id to send the message to
void message_sending_send_sdp_message(
        sdp_msg_pure_data* my_msg, int processor_id){
    // print message completley for proof its working
    log_debug("message address is %x", my_msg);
    log_debug("length = %x", my_msg->length);
    log_debug("checksum = %x", my_msg->checksum);
    log_debug("flags = %u", my_msg->flags);
    log_debug("tag = %u", my_msg->tag);
    log_debug("dest_port = %u", my_msg->dest_port);
    log_debug("srce_port = %u", my_msg->srce_port);
    log_debug("dest_addr = %u", my_msg->dest_addr);
    log_debug("srce_addr = %u", my_msg->srce_addr);
    log_debug("data 0 = %d", my_msg->data[0]);
    log_debug("data 1 = %d", my_msg->data[1]);
    log_debug("data 2 = %d", my_msg->data[2]);

    uint32_t attempt = 0;
    log_debug("sending message");
    //bool received = false;
    //while (!received){
        while (!spin1_send_sdp_msg((sdp_msg_t *) my_msg, _SDP_TIMEOUT)) {
            attempt += 1;
            log_debug("failed to send. trying again");
            if (attempt >= 30) {
                rt_error(RTE_SWERR);
                malloc_extras_terminate(EXIT_FAIL);
            }
        }

        // give chance for compressor to read
        //spin1_delay_us(50);

        //vcpu_t *sark_virtual_processor_info = (vcpu_t*) SV_VCPU;
        //vcpu_t *comp_processor = &sark_virtual_processor_info[processor_id];
        //if (comp_processor->user1 == 1){
        //    received = true;
        //}
    //}
    log_debug("sent message");
}

//! \brief frees SDRAM from the compressor processor.
//! \param[in] processor_index: the compressor processor index to clear
//! SDRAM usage from
//! \param[in] processor_bf_tables: the map of what tables that processor used
//! \return bool stating that it was successful in clearing SDRAM
bool free_sdram_from_compression_attempt(comp_instruction_t* instuctions) {
    int elements = processor_bf_tables[processor_id].n_elements;

    log_error("method needs checking and not surigually removed");
    return true;

    // free the individual elements
    for (int bit_field_id = 0; bit_field_id < elements; bit_field_id++) {
        FREE(processor_bf_tables[processor_id].elements[bit_field_id]);
    }

    // only try freeing if its not been freed already. (safety feature)
    if (processor_bf_tables[processor_id].elements != NULL){
        FREE(processor_bf_tables[processor_id].elements);
    }

    processor_bf_tables[processor_id].elements = NULL;
    processor_bf_tables[processor_id].n_elements = 0;
    processor_bf_tables[processor_id].n_bit_fields = 0;
    return true;
}


//! \brief update the mc message to point at right direction
//! \param[in] processor_id: the compressor processor id.
//! \param[in] my_msg: sdp message
static inline void update_mc_message(
        int processor_id, sdp_msg_pure_data* my_msg) {
    my_msg->srce_addr = spin1_get_chip_id();
    my_msg->dest_addr = spin1_get_chip_id();
    my_msg->flags = REPLY_NOT_EXPECTED;
    my_msg->srce_port = (RANDOM_PORT << PORT_SHIFT) | spin1_get_core_id();
    my_msg->dest_port = (RANDOM_PORT << PORT_SHIFT) | processor_id;
}

//! \brief sets up the packet to fly to the compressor processor
//! \param[in]
//! \param[in] my_msg: sdp message to send
//! \param[in] usable_sdram_regions: sdram for fake heap for compressor
static void set_up_packet(
        comp_processor_store_t* data_store, sdp_msg_pure_data* my_msg) {

    // create cast
    start_sdp_packet_t *data = (start_sdp_packet_t*) &my_msg->data;

    // fill in
    data->command_code = START_DATA_STREAM;
    data->fake_heap_data = malloc_extras_get_stolen_heap();
    data->table_data = data_store;
    my_msg->length = (LENGTH_OF_SDP_HEADER + sizeof(start_sdp_packet_t));
}

//! \brief sets off the basic compression without any bitfields
//! \param[in] processors_bf_tables: metadata holder of compressor processors
//! such as the routing tables used in its attempt.
//! \param[in] my_msg: sdp message to send
//! \param[in] usable_sdram_regions: the data for fake heap to send to the
//! compressor.
//! \param[in] uncompressed_router_table: uncompressed router table in SDRAM.
//! \param[in] processor_id: The processor id to use
//! \return bool saying if the memory allocations were successful and packet
//! sent. false otherwise.
bool message_sending_set_off_no_bit_field_compression(
        uncompressed_table_region_data_t *uncompressed_router_table,
        int processor_id) {

    // allocate and clone uncompressed entry
    log_info("start cloning of uncompressed table");
    table_t *sdram_clone_of_routing_table =
        helpful_functions_clone_un_compressed_routing_table(
            uncompressed_router_table);

    if (sdram_clone_of_routing_table == NULL){
        log_error("could not allocate memory for uncompressed table for no "
                  "bit field compression attempt.");
        return false;
    }
    log_info("finished cloning of uncompressed table");

    // set up the bitfield routing tables so that it'll map down below
    table_t **bit_field_routing_tables = MALLOC_SDRAM(sizeof(table_t*));
    if (bit_field_routing_tables == NULL){
        log_error(
            "failed to allocate memory for the bit_field_routing tables");
        return false;
    }

    bit_field_routing_tables[0] = sdram_clone_of_routing_table;
    log_info("allocated bf routing tables");
    log_info(
        "size of the first table is %d", bit_field_routing_tables[0]->size);

    // run the allocation and set off of a compressor processor
    return message_sending_set_off_bit_field_compression(
        N_UNCOMPRESSED_TABLE, 0, bit_field_routing_tables, processor_id);
}

#endif  // __MESSAGE_SENDING_H__
