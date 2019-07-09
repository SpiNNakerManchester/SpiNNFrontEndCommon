/*! \file
 *
 *  \brief implementation of recording.h
 *
 */

#include <recording.h>
#include <simulation.h>
#include <buffered_eieio_defs.h>
#include <simulation.h>
#include <sark.h>
#include <circular_buffer.h>
#include <spin1_api_params.h>

// Declare wfi function
extern void spin1_wfi();

// Standard includes
#include <debug.h>

//---------------------------------------
// Structures
//---------------------------------------
//! structure that defines a channel in memory.
typedef struct recording_channel_t {
    uint8_t *start;
    uint8_t *current_write;
    uint8_t *dma_current_write;
    uint8_t *current_read;
    uint8_t *end;
    uint8_t region_id;
    uint8_t missing_info;
    buffered_operations last_buffer_operation;
} recording_channel_t;

struct recording_data_t {
    uint32_t n_regions;
    uint32_t tag;
    uint32_t tag_destination;
    uint32_t sdp_port;
    uint32_t buffer_size_before_request;
    uint32_t time_between_triggers;
    uint32_t last_sequence_number;
    recording_channel_t *region_pointers[0];
};

//---------------------------------------
// Globals
//---------------------------------------

//! circular queue for DMA complete addresses
static circular_buffer dma_complete_buffer;

//! array containing all possible channels. In DTCM.
static recording_channel_t *recording_channels = NULL;
//! array containing all possible channels. Array in DTCM; channel structures in SDRAM.
static recording_channel_t **region_addresses = NULL;
static uint32_t *region_sizes = NULL;
static uint32_t n_recording_regions = 0;
static uint32_t sdp_port = 0;
static uint32_t sequence_number = 0;
static bool sequence_ack = false;
static uint32_t last_time_buffering_trigger = 0;
static uint32_t buffer_size_before_trigger = 0;
static uint32_t time_between_triggers = 0;

// A pointer to the last sequence number to write once recording is complete
static uint32_t *last_sequence_number;

//! An SDP Message and parts
static sdp_msg_t msg;
static read_request_packet_header *req_hdr;
static read_request_packet_data *data_ptr;

//! The time between buffer read messages
#define MIN_TIME_BETWEEN_TRIGGERS 50

//---------------------------------------
// Private method
//---------------------------------------
//! \brief checks that a channel has been initialised
//! \param[in] channel_idx the channel to check
//! \return True if the channel has been initialised or false otherwise
static inline bool has_been_initialsed(uint8_t channel_idx) {
    return recording_channels[channel_idx].start != NULL;
}

//----------------------------------------
//  Private method
//----------------------------------------
//! \brief closes a channel
//! \param[in] channel_idx the channel to close
//! \return True if the channel was successfully closed and False otherwise.
static inline bool close_channel(uint8_t channel_idx) {
    recording_channel_t *channel = &recording_channels[channel_idx];
    channel->start = NULL;
    channel->end = NULL;
    return true;
}

typedef struct host_data_read_packet {
    host_data_read_packet_header hdr;
    host_data_read_packet_data data[];
} host_data_read_packet;

static inline void host_data_read(host_data_read_packet *msg) {
    uint8_t n_requests = msg->hdr.request;
    uint8_t sequence = msg->hdr.sequence;
    host_data_read_packet_data *data = msg->data;

    if (sequence != sequence_number) {
        log_debug("dropping packet with sequence no: %d", sequence);
        return;
    }
    sequence_number = (sequence_number + 1) & MAX_SEQUENCE_NO;
    sequence_ack = false;

    uint32_t i;
    for (i = 0; i < n_requests; i++) {
        uint8_t channel_idx = data[i].channel;
        uint32_t space_read = data[i].space_read;
        recording_channel_t *channel = &recording_channels[channel_idx];

        uint8_t *temp_value = channel->current_read + space_read;

        log_debug("channel %d, updating read pointer by %d bytes, from 0x%08x",
                channel_idx, space_read, channel->current_read);
        if (temp_value >= channel->end) {
            temp_value -= channel->end - channel->start;
            log_debug("channel %d, read wrap around", channel_idx);
        }

        channel->current_read = temp_value;
        channel->last_buffer_operation = BUFFER_OPERATION_READ;
    }
}

static inline void host_data_read_ack(
        host_data_read_ack_packet_header *msg) {
    uint8_t sequence = msg->sequence;

    if (sequence != sequence_number) {
        log_debug("dropping packet with sequence no: %d", sequence);
        return;
    }
    log_debug("Sequence %d acked", sequence);
    sequence_ack = true;
}

static inline void eieio_packet_handler(eieio_msg_t msg, uint length) {
    uint16_t data_hdr_value = msg[0];
    uint8_t pkt_type = (data_hdr_value >> 14) & 0x03;
    uint16_t pkt_command = data_hdr_value & ~0xC000;

    log_debug("received packet of type %d", pkt_type);

    if (pkt_type == 0x01) {
        log_debug("recording - parsing a command packet");
        switch (pkt_command) {
        case HOST_DATA_READ:
            log_debug("command: HOST_DATA_READ");
            host_data_read((host_data_read_packet *) msg);
            break;

        case HOST_DATA_READ_ACK:
            log_debug("command: HOST_DATA_READ_ACK");
            host_data_read_ack((host_data_read_ack_packet_header *) msg);
            break;

        default:
            log_debug("unhandled command ID %d", pkt_command);
            break;
        }
    }

    log_debug("leaving packet handler");
}

// Work out the space available in the given channel for recording
static uint32_t compute_available_space_in_channel(uint8_t channel_idx) {
    const recording_channel_t *channel = &recording_channels[channel_idx];
    const uint8_t *buffer_region = channel->start;
    const uint8_t *end_of_region = channel->end;
    const uint8_t *write_pointer = channel->current_write;
    const uint8_t *read_pointer = channel->current_read;
    buffered_operations last_operation = channel->last_buffer_operation;

    if (read_pointer < write_pointer) {
        uint32_t final_space = (uint32_t) (end_of_region - write_pointer);
        uint32_t initial_space = (uint32_t) (read_pointer - buffer_region);
        return final_space + initial_space;
    } else if (write_pointer < read_pointer) {
        return read_pointer - write_pointer;
    } else if (last_operation == BUFFER_OPERATION_WRITE) {
        // If pointers are equal, buffer is full if last operation is write
        return 0;
    } else {
        // If last operation is read, buffer is empty if pointers are equal
        return end_of_region - buffer_region;
    }
}

static void do_write(
        uint8_t channel_idx, void *data, void *write_pointer, uint32_t length,
        void *finished_write_pointer, recording_complete_callback_t callback) {
    if (callback != NULL) {
        // add to DMA complete tracker
        circular_buffer_add(dma_complete_buffer, (uint32_t) channel_idx);
        circular_buffer_add(
                dma_complete_buffer, (uint32_t) finished_write_pointer);
        circular_buffer_add(dma_complete_buffer, (uint32_t) callback);

        // set off DMA - if not accepted, wait until another DMA is done
        while (!spin1_dma_transfer(
                RECORDING_DMA_COMPLETE_TAG_ID, write_pointer, data, DMA_WRITE,
                length)) {
            spin1_wfi();
        }
    } else {
        spin1_memcpy(write_pointer, data, length);
        recording_channels[channel_idx].dma_current_write =
                finished_write_pointer;
    }
}

// Add a packet to the SDRAM
static inline bool write_memory(
        uint8_t channel_idx, void *data, uint32_t length,
        recording_complete_callback_t callback) {
    recording_channel_t *channel = &recording_channels[channel_idx];
    uint8_t *buffer_region = channel->start;
    const uint8_t *end_of_region = channel->end;
    uint8_t *write_pointer = channel->current_write;
    const uint8_t *read_pointer = channel->current_read;
    buffered_operations last_operation = channel->last_buffer_operation;

    log_debug("t = %u, channel = %u, start = 0x%08x, read = 0x%08x,"
            "write = 0x%08x, end = 0x%08x, operation == read = %u, len = %u",
            spin1_get_simulation_time(), channel_idx, buffer_region,
            read_pointer, write_pointer, end_of_region,
            last_operation == BUFFER_OPERATION_READ, length);

    if ((read_pointer < write_pointer) ||
           (read_pointer == write_pointer &&
                   last_operation == BUFFER_OPERATION_READ)) {
        uint32_t final_space = (uint32_t) (end_of_region - write_pointer);

        if (final_space >= length) {
            log_debug("Packet fits in final space of %u", final_space);
            do_write(channel_idx, data, write_pointer, length,
                    write_pointer + length, callback);
            write_pointer += length;
        } else {
            uint32_t total_space =
                    final_space + (uint32_t) (read_pointer - buffer_region);
            if (total_space < length) {
                log_debug("Not enough space in final area (%u bytes)", total_space);
                return false;
            }

            log_debug("Copying first %d bytes to final space of %u", final_space);

            do_write(channel_idx, data, write_pointer, final_space,
                    buffer_region, NULL);

            write_pointer = buffer_region;
            data += final_space;

            uint32_t final_len = length - final_space;
            log_debug("Copying remaining %u bytes", final_len);

            do_write(channel_idx, data, write_pointer, final_len,
                    write_pointer + final_len, callback);

            write_pointer += final_len;
        }
    } else if (write_pointer < read_pointer) {
        uint32_t middle_space = (uint32_t) (read_pointer - write_pointer);

        if (middle_space < length) {
            log_debug("Not enough space in middle (%u bytes)", middle_space);
            return false;
        }

        log_debug("Packet fits in middle space of %u", middle_space);
        do_write(channel_idx, data, write_pointer, length,
                write_pointer + length, callback);
        write_pointer += length;
    } else {
        log_debug("reached end");

        log_debug("Buffer already full");
        return false;
    }

    if (write_pointer == end_of_region) {
        write_pointer = buffer_region;
        log_debug("channel %u, write wrap around", channel_idx);
    }
    channel->current_write = write_pointer;
    channel->last_buffer_operation = BUFFER_OPERATION_WRITE;
    return true;
}

static void create_buffer_message(
        read_request_packet_data *data_ptr,
        uint channel_idx, const uint8_t *read_pointer,
        uint32_t space_to_be_read) {
    data_ptr->processor_and_request = 0;
    data_ptr->sequence = 0;
    data_ptr->channel = channel_idx;
    data_ptr->region = recording_channels[channel_idx].region_id;
    data_ptr->start_address = (uint32_t) read_pointer;
    data_ptr->space_to_be_read = space_to_be_read;
}

static inline void send_buffering_out_trigger_message(
        bool flush_all) {
    uint msg_size = 16 + sizeof(read_request_packet_header);
    uint n_requests = 0;

    for (uint i = 0; i < n_recording_regions; i++) {
        recording_channel_t *channel = &recording_channels[i];
        uint32_t space_total = channel->end - channel->start;
        uint32_t space_available = compute_available_space_in_channel(i);

        if (has_been_initialsed(i) && (flush_all ||
                space_total - space_available >= buffer_size_before_trigger)) {
            uint8_t *buffer_region = channel->start;
            const uint8_t *end_of_region = channel->end;
            uint8_t *write_pointer = channel->dma_current_write;
            const uint8_t *read_pointer = channel->current_read;
            buffered_operations last_operation = channel->last_buffer_operation;

            if (read_pointer < write_pointer) {
                create_buffer_message(&data_ptr[n_requests], i, read_pointer,
                        write_pointer - read_pointer);
                n_requests++;
            } else if ((write_pointer < read_pointer) ||
                    (write_pointer == read_pointer &&
                     last_operation == BUFFER_OPERATION_WRITE)) {
                create_buffer_message(&data_ptr[n_requests], i, read_pointer,
                        end_of_region - read_pointer);
                n_requests++;

                create_buffer_message(&data_ptr[n_requests], i, buffer_region,
                        write_pointer - buffer_region);
                n_requests++;
            } else {
                /* something somewhere went terribly wrong this should never
                 * happen */
                log_error("Unknown channel state - channel: %d, start pointer: %d,"
                        " end pointer: %d, read_pointer: %d, write_pointer: %d,"
                        " last operation==READ: %d", i, buffer_region,
                        end_of_region, read_pointer, write_pointer,
                        last_operation == BUFFER_OPERATION_READ);
            }
        }
    }

    if (n_requests > 0) {
        // eieio command packet with command ID 8
        req_hdr->eieio_header_command = 0x4008;
        req_hdr->chip_id = spin1_get_chip_id();
        data_ptr[0].processor_and_request =
                (spin1_get_core_id() << 3) | n_requests;
        data_ptr[0].sequence = sequence_number;
        log_debug("Sending request with sequence %d", sequence_number);
        msg_size += n_requests * sizeof(read_request_packet_data);
        msg.length = msg_size;

        spin1_send_sdp_msg(&msg, 1);
    }
}

static void buffering_in_handler(uint mailbox, uint port) {
    use(port);
    sdp_msg_t *msg = (sdp_msg_t *) mailbox;

    eieio_packet_handler((eieio_msg_t) &msg->cmd_rc, msg->length - 8);

    log_debug("Freeing message");
    spin1_msg_free(msg);
    log_debug("Done freeing message");
}

bool recording_record_and_notify(
        uint8_t channel_idx, void *data, uint32_t size_bytes,
        recording_complete_callback_t callback) {
    if (has_been_initialsed(channel_idx)) {
        uint32_t space_available =
                compute_available_space_in_channel(channel_idx);

        // If there's space to record
        if (space_available >= size_bytes) {
            // Copy data into recording channel
            write_memory(channel_idx, data, size_bytes, callback);
            return true;
        }

        if (!recording_channels[channel_idx].missing_info) {
            log_info("WARNING: recording channel %u out of space", channel_idx);
            recording_channels[channel_idx].missing_info = 1;
        }
    }

    // Call the callback to make sure resources are freed
    if (callback != NULL) {
        callback();
    }
    return false;
}

bool recording_record(uint8_t channel, void *data, uint32_t size_bytes) {
    // Because callback is NULL, spin1_memcpy will be used
    return recording_record_and_notify(channel, data, size_bytes, NULL);
}

//! \brief this writes the state data to the regions
static void buffer_state_data_write(void) {
    for (uint32_t i = 0; i < n_recording_regions; i++) {
        recording_channel_t *recording_region_address =
                region_addresses[i];
        spin1_memcpy(recording_region_address, &recording_channels[i],
                sizeof(recording_channel_t));
        log_debug("Storing channel %d state info starting at 0x%08x",
                i, recording_region_address);
    }

    /* store info related to the state of the transmission to avoid possible
     * duplication of info on the host side */
    *last_sequence_number = sequence_number;
}

void recording_finalise(void) {
    log_debug("Finalising recording channels");

    // wait till all DMA's have been finished
    while (circular_buffer_size(dma_complete_buffer) != 0) {
        spin1_wfi();
    }

    // update buffer state data write
    buffer_state_data_write();

    // Loop through channels
    for (uint32_t i = 0; i < n_recording_regions; i++) {
        // If this channel's in use
        if (has_been_initialsed(i)) {
            recording_channel_t *channel = &recording_channels[i];

            /* Calculate the number of bytes that have been written and write
             * back to SDRAM counter */
            if (channel->missing_info) {
                log_info("\tFinalising channel %u - dropped information while"
                        "buffering - state info stored in SDRAM", i);
            } else {
                log_info("\tFinalising channel %u - state info stored in SDRAM",
                        i);
            }
            if (!close_channel(i)) {
                log_error("could not close channel %u.", i);
            } else {
                log_info("closed channel %u.", i);
            }
        }
    }
}

//! \brief updates host read point as DMA has finished
static void dma_finished(uint unused, uint tag) {
    // pop region and write pointer from circular queue
    uint32_t channel_idx, dma_current_write, callback_address;

    circular_buffer_get_next(dma_complete_buffer, &channel_idx);
    circular_buffer_get_next(dma_complete_buffer, &dma_current_write);
    circular_buffer_get_next(dma_complete_buffer, &callback_address);

    recording_complete_callback_t callback =
            (recording_complete_callback_t) callback_address;

    // update recording region dma_current_write
    recording_channels[channel_idx].dma_current_write =
            (uint8_t *) dma_current_write;

    if (callback != NULL) {
        callback();
    }
}

bool recording_initialize(
        address_t recording_config_address, uint32_t *recording_flags) {
    struct recording_data_t *config =
            (struct recording_data_t *) recording_config_address;

    // build DMA address circular queue
    dma_complete_buffer = circular_buffer_initialize(DMA_QUEUE_SIZE * 4);

    // Read in the parameters
    n_recording_regions = config->n_regions;
    uint8_t buffering_output_tag = config->tag;
    uint32_t buffering_destination = config->tag_destination;
    sdp_port = config->sdp_port;
    buffer_size_before_trigger = config->buffer_size_before_request;
    time_between_triggers = config->time_between_triggers;
    if (time_between_triggers < MIN_TIME_BETWEEN_TRIGGERS) {
        time_between_triggers = MIN_TIME_BETWEEN_TRIGGERS;
    }
    last_sequence_number = &config->last_sequence_number;

    log_info("Recording %d regions, using output tag %d, size before trigger %d, "
            "time between triggers %d",
            n_recording_regions, buffering_output_tag, buffer_size_before_trigger,
            time_between_triggers);

    // Set up the space for holding recording pointers and sizes
    region_addresses = spin1_malloc(
            n_recording_regions * sizeof(recording_channel_t *));
    if (region_addresses == NULL) {
        log_error("Not enough space to allocate recording addresses");
        return false;
    }
    region_sizes = spin1_malloc(n_recording_regions * sizeof(uint32_t));
    if (region_sizes == NULL) {
        log_error("Not enough space to allocate region sizes");
        return false;
    }

    // Set up the recording flags
    if (recording_flags != NULL) {
        *recording_flags = 0;
    }

    /* Reserve the actual recording regions.
     *
     * An extra sizeof(recording_channel_t) bytes are reserved per channel
     * to store the data after recording */
    uint32_t *sizes = (uint32_t *)
            &config->region_pointers[n_recording_regions];
    for (uint32_t i = 0; i < n_recording_regions; i++) {
        uint32_t size = sizes[i];
        if (size == 0) {
            region_addresses[i] = NULL;
        } else {
            region_addresses[i] = sark_xalloc(
                    sv->sdram_heap, size + sizeof(recording_channel_t), 0,
                    ALLOC_LOCK + ALLOC_ID + (sark_vec->app_id << 8));
            if (region_addresses[i] == NULL) {
                log_error("Could not allocate recording region %u of %u bytes",
                        i, size);
                return false;
            }
            if (recording_flags) {
                *recording_flags |= 1 << i;
            }
        }
        region_sizes[i] = size;
        config->region_pointers[i] = region_addresses[i];
    }
    recording_channels = spin1_malloc(
            n_recording_regions * sizeof(recording_channel_t));
    if (!recording_channels) {
        log_error("Not enough space to create recording channels");
        return false;
    }
    log_debug("Allocated recording channels to 0x%08x", recording_channels);

    // Set up the channels and write the initial state data
    recording_reset();

    // Set up the buffer message
    req_hdr = (read_request_packet_header *) &msg.cmd_rc;
    data_ptr = (read_request_packet_data *) &req_hdr[1];
    msg.flags = 0x7;
    msg.tag = buffering_output_tag;
    msg.dest_port = 0xFF;
    msg.srce_port = (sdp_port << 5) | spin1_get_core_id();
    msg.dest_addr = buffering_destination;
    msg.srce_addr = spin1_get_chip_id();

    // register the SDP handler
    simulation_sdp_callback_on(sdp_port, buffering_in_handler);

    // register DMA transfer done callback
    simulation_dma_transfer_done_callback_on(
            RECORDING_DMA_COMPLETE_TAG_ID, dma_finished);

    return true;
}

void recording_reset(void) {
    // Go through the regions and set up the data
    for (uint32_t i = 0; i < n_recording_regions; i++) {
        uint32_t region_size = region_sizes[i];
        recording_channel_t *channel = &recording_channels[i];
        log_debug("region size %d", region_size);
        if (region_size > 0) {
            recording_channel_t *region_ptr = region_addresses[i];

            log_debug("%d is size of buffer state in words",
                    sizeof(recording_channel_t) / sizeof(address_t));

            uint8_t *region_data_address = (uint8_t *) &region_ptr[1];

            // store pointers to the start, current position and end of this
            channel->start = region_data_address;
            channel->current_write = region_data_address;
            channel->dma_current_write = region_data_address;
            channel->current_read = region_data_address;
            channel->end = region_data_address + region_size;

            log_info("Recording channel %u configured to use %u byte memory "
                    "block starting at 0x%08x", i, region_size,
                    channel->start);
        } else {
            channel->start = NULL;
            channel->current_write = NULL;
            channel->dma_current_write = NULL;
            channel->current_read = NULL;
            channel->end = NULL;

            log_info("Recording channel %u left uninitialised", i);
        }
        channel->last_buffer_operation = BUFFER_OPERATION_READ;
        channel->region_id = i;
        channel->missing_info = 0;
    }
    buffer_state_data_write();
    sequence_number = 0;
    sequence_ack = false;
}

void recording_do_timestep_update(uint32_t time) {
    if (!sequence_ack &&
            ((time - last_time_buffering_trigger) > time_between_triggers)) {
        log_debug("Sending buffering trigger message");
        send_buffering_out_trigger_message(0);
        last_time_buffering_trigger = time;
    }
}
