/*! \file
 *
 *  \brief implementation of recording.h
 *
 */

#include <recording.h>
#include <simulation.h>
#include <buffered_eieio_defs.h>

#include <sark.h>

// Standard includes
#include <string.h>
#include <debug.h>

enum recording_data_e {
    N_REGIONS,
    TAG,
    TAG_DESTINATION,
    SDP_PORT,
    BUFFER_SIZE_BEFORE_REQUEST,
    TIME_BETWEEN_TRIGGERS,
    LAST_SEQUENCE_NUMBER,
    REGION_POINTERS_START
};

//---------------------------------------
// Structures
//---------------------------------------
//! structure that defines a channel in memory.
typedef struct recording_channel_t {
    uint8_t *start;
    uint8_t *current_write;
    uint8_t *current_read;
    uint8_t *end;
    uint8_t region_id;
    uint8_t missing_info;
    buffered_operations last_buffer_operation;
} recording_channel_t;

//---------------------------------------
// Globals
//---------------------------------------
//! array containing all possible channels.
static recording_channel_t *g_recording_channels = NULL;
static address_t *region_addresses = NULL;
static uint32_t *region_sizes = NULL;
static uint32_t n_recording_regions = 0;
static uint32_t sdp_port = 0;
static uint32_t sequence_number = 0;
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
//! \param[in] channel the channel to check
//! \return True if the channel has been initialised or false otherwise
static inline bool _has_been_initialsed(uint8_t channel) {
    return g_recording_channels[channel].start != NULL;
}

//----------------------------------------
//  Private method
//----------------------------------------
//! \brief closes a channel
//! \param[in] channel the channel to close
//! \return True if the channel was successfully closed and False otherwise.
static inline bool _close_channel(uint8_t channel) {
    g_recording_channels[channel].start = NULL;
    g_recording_channels[channel].end = NULL;
    return true;
}

static inline void _recording_host_data_read(eieio_msg_t msg, uint length) {
    host_data_read_packet_header *ptr_hdr =
        (host_data_read_packet_header *) msg;
    host_data_read_packet_data *ptr_data =
        (host_data_read_packet_data *) (&ptr_hdr[1]);

    uint8_t n_requests = ptr_hdr->request;
    uint8_t sequence = ptr_hdr->sequence;

    uint32_t i;

    if (sequence != sequence_number) {
        log_debug("dropping packet with sequence no: %d", sequence);
        return;
    }
    sequence_number = (sequence_number + 1) & MAX_SEQUENCE_NO;

    for (i = 0; i < n_requests; i++) {
        uint8_t channel = ptr_data[i].channel;
        uint32_t space_read = ptr_data[i].space_read;

        uint32_t temp_value = (uint32_t) (
            g_recording_channels[channel].current_read + space_read);

        log_debug(
            "channel %d, updating read pointer by %d bytes, from 0x%08x",
            channel, space_read, g_recording_channels[channel].current_read);
        if (temp_value >= (uint32_t) g_recording_channels[channel].end) {
            uint32_t channel_space_total = (uint32_t) (
                g_recording_channels[channel].end -
                g_recording_channels[channel].start);
            temp_value = temp_value - channel_space_total;
            log_debug("channel %d, read wrap around", channel);
        }

        g_recording_channels[channel].current_read = (uint8_t *) temp_value;
        g_recording_channels[channel].last_buffer_operation =
            BUFFER_OPERATION_READ;
    }
}

static inline void _recording_eieio_packet_handler(
        eieio_msg_t msg, uint length) {
    uint16_t data_hdr_value = msg[0];
    uint8_t pkt_type = (data_hdr_value >> 14) && 0x03;
    uint16_t pkt_command = data_hdr_value & (~0xC000);

    log_debug("received packet of type %d", pkt_type);

    if (pkt_type == 0x01) {
        log_debug("recording - parsing a command packet");
        switch (pkt_command) {
        case HOST_DATA_READ:
            log_debug("command: HOST_DATA_READ");
            _recording_host_data_read(msg, length);
            break;

        default:
            log_debug("unhandled command id %d", pkt_command);
            break;
        }
    }

    log_debug("leaving packet handler");
}

// Work out the space available in the given channel for recording
static uint32_t compute_available_space_in_channel(uint8_t channel) {
    uint8_t *buffer_region = g_recording_channels[channel].start;
    uint8_t *end_of_buffer_region = g_recording_channels[channel].end;
    uint8_t *write_pointer = g_recording_channels[channel].current_write;
    uint8_t *read_pointer = g_recording_channels[channel].current_read;
    buffered_operations last_buffer_operation =
        g_recording_channels[channel].last_buffer_operation;

    if (read_pointer < write_pointer) {
        uint32_t final_space =
            (uint32_t) end_of_buffer_region - (uint32_t) write_pointer;
        uint32_t initial_space =
            (uint32_t) read_pointer - (uint32_t) buffer_region;
        return final_space + initial_space;
    } else if (write_pointer < read_pointer) {
        return (uint32_t) read_pointer - (uint32_t) write_pointer;
    } else if (last_buffer_operation == BUFFER_OPERATION_WRITE) {

        // If pointers are equal, buffer is full if last operation is write
        return 0;
    } else {

        // If pointers are equal, buffer is empty if last operation is read
        return (end_of_buffer_region - buffer_region);
    }
}

// Add a packet to the SDRAM
static inline bool _recording_write_memory(
        uint8_t channel, void *data, uint32_t length) {
    uint8_t *buffer_region = g_recording_channels[channel].start;
    uint8_t *end_of_buffer_region = g_recording_channels[channel].end;
    uint8_t *write_pointer = g_recording_channels[channel].current_write;
    uint8_t *read_pointer = g_recording_channels[channel].current_read;
    buffered_operations last_buffer_operation =
        g_recording_channels[channel].last_buffer_operation;

    log_debug("t = %u, channel = %u, start = 0x%08x, read = 0x%08x,"
              "write = 0x%08x, end = 0x%08x, operation == read = %u, len = %u",
              spin1_get_simulation_time(), channel, buffer_region,
              read_pointer, write_pointer, end_of_buffer_region,
              last_buffer_operation == BUFFER_OPERATION_READ, length);

    if ((read_pointer < write_pointer) ||
           (read_pointer == write_pointer &&
               last_buffer_operation == BUFFER_OPERATION_READ)) {
        uint32_t final_space =
            (uint32_t) end_of_buffer_region - (uint32_t) write_pointer;

        if (final_space >= length) {
            log_debug("Packet fits in final space of %u", final_space);
            spin1_memcpy(write_pointer, data, length);
            write_pointer += length;
            if (write_pointer >= end_of_buffer_region) {
                write_pointer = buffer_region;
                log_debug("channel %u, write wrap around", channel);
            }
            g_recording_channels[channel].current_write = write_pointer;
            g_recording_channels[channel].last_buffer_operation =
                BUFFER_OPERATION_WRITE;
            return true;
        } else {

            uint32_t total_space =
                final_space +
                ((uint32_t) read_pointer - (uint32_t) buffer_region);
            if (total_space < length) {
                log_debug(
                    "Not enough space in final area (%u bytes)", total_space);
                return false;
            }

            log_debug(
                "Copying first %d bytes to final space of %u", final_space);
            spin1_memcpy(write_pointer, data, final_space);
            write_pointer = buffer_region;
            data += final_space;

            uint32_t final_len = length - final_space;
            log_debug("Copying remaining %u bytes", final_len);
            spin1_memcpy(write_pointer, data, final_len);
            write_pointer += final_len;
            if (write_pointer == end_of_buffer_region) {
                write_pointer = buffer_region;
                log_debug("channel %u, write wrap around", channel);
            }
            g_recording_channels[channel].current_write = write_pointer;
            g_recording_channels[channel].last_buffer_operation =
                BUFFER_OPERATION_WRITE;
            return true;
        }
    } else if (write_pointer < read_pointer) {
        uint32_t middle_space =
            (uint32_t) read_pointer - (uint32_t) write_pointer;

        if (middle_space < length) {
            log_debug("Not enough space in middle (%u bytes)", middle_space);
            return false;
        } else {
            log_debug("Packet fits in middle space of %u", middle_space);
            spin1_memcpy(write_pointer, data, length);
            write_pointer += length;
            if (write_pointer == end_of_buffer_region) {
                write_pointer = buffer_region;
                log_debug("channel %u, write wrap around", channel);
            }
            g_recording_channels[channel].current_write = write_pointer;
            g_recording_channels[channel].last_buffer_operation =
                BUFFER_OPERATION_WRITE;
            return true;
        }
    }
    log_debug("reached end");

    log_debug("Buffer already full");
    return false;

}

static void _create_buffer_message(
        read_request_packet_data *data_ptr, uint n_requests,
        uint channel, uint8_t *read_pointer, uint32_t space_to_be_read) {
    data_ptr[n_requests].processor_and_request = 0;
    data_ptr[n_requests].sequence = 0;
    data_ptr[n_requests].channel = channel;
    data_ptr[n_requests].region =
        g_recording_channels[channel].region_id;
    data_ptr[n_requests].start_address = (uint32_t) read_pointer;
    data_ptr[n_requests].space_to_be_read = space_to_be_read;
}

static inline void _recording_send_buffering_out_trigger_message(
        bool flush_all) {

    uint msg_size = 16 + sizeof(read_request_packet_header);
    uint n_requests = 0;

    for (uint channel = 0; channel < n_recording_regions; channel++) {
        uint32_t channel_space_total =
            (uint32_t) (g_recording_channels[channel].end -
                        g_recording_channels[channel].start);
        uint32_t channel_space_available = compute_available_space_in_channel(
                channel);

        if (_has_been_initialsed(channel) && (flush_all ||
                (channel_space_total - channel_space_available) >=
                     buffer_size_before_trigger)) {
            uint8_t *buffer_region = g_recording_channels[channel].start;
            uint8_t *end_of_buffer_region = g_recording_channels[channel].end;
            uint8_t *write_pointer = g_recording_channels[channel].current_write;
            uint8_t *read_pointer = g_recording_channels[channel].current_read;
            buffered_operations last_buffer_operation =
                g_recording_channels[channel].last_buffer_operation;

            if (read_pointer < write_pointer) {
                _create_buffer_message(
                    data_ptr, n_requests, channel, read_pointer,
                    write_pointer - read_pointer);
                n_requests++;
            } else if ((write_pointer < read_pointer) ||
                    (write_pointer == read_pointer &&
                     last_buffer_operation == BUFFER_OPERATION_WRITE)) {
                _create_buffer_message(
                    data_ptr, n_requests, channel, read_pointer,
                    end_of_buffer_region - read_pointer);
                n_requests++;

                _create_buffer_message(
                    data_ptr, n_requests, channel, buffer_region,
                    write_pointer - buffer_region);
                n_requests++;
            } else {

                // something somewhere went terribly wrong this should never
                // happen
                log_error(
                    "Unknown channel state - channel: %d, start pointer: %d,"
                    " end pointer: %d, read_pointer: %d, write_pointer: %d,"
                    " last operation==READ: %d", channel, buffer_region,
                    end_of_buffer_region, read_pointer, write_pointer,
                    last_buffer_operation == BUFFER_OPERATION_READ);
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
        msg_size += (n_requests * sizeof(read_request_packet_data));
        msg.length = msg_size;

        spin1_send_sdp_msg(&msg, 1);
    }
}

static void _buffering_in_handler(uint mailbox, uint port) {
    use(port);
    sdp_msg_t *msg = (sdp_msg_t *) mailbox;
    uint16_t length = msg->length;
    eieio_msg_t eieio_msg_ptr = (eieio_msg_t) &(msg->cmd_rc);

    _recording_eieio_packet_handler(eieio_msg_ptr, length - 8);

    log_debug("Freeing message");
    spin1_msg_free(msg);
    log_debug("Done freeing message");
}

bool recording_record(uint8_t channel, void *data, uint32_t size_bytes) {

    if (_has_been_initialsed(channel)) {
        recording_channel_t *recording_channel = &g_recording_channels[channel];
        uint32_t space_available = compute_available_space_in_channel(channel);

        // If there's space to record
        if (space_available >= size_bytes) {

            // Copy data into recording channel
            _recording_write_memory(channel, data, size_bytes);

            return true;
        } else {
            if (!g_recording_channels[channel].missing_info) {
                log_info("WARNING: recording channel %u out of space", channel);
                g_recording_channels[channel].missing_info = 1;
            }
            return false;
        }
    } else {
        return false;
    }
}

//! brief this writes the state data to the regions
void _recording_buffer_state_data_write(){
    for (uint32_t recording_region_id = 0;
             recording_region_id < n_recording_regions;
             recording_region_id++) {
        address_t recording_region_address =
            region_addresses[recording_region_id];
        spin1_memcpy(
             recording_region_address,
             &g_recording_channels[recording_region_id],
             sizeof(recording_channel_t));
        log_debug(
             "Storing channel state info starting at 0x%08x",
             recording_region_address);
    }

    // store info related to the state of the transmission to avoid possible
    // duplication of info on the host side
    *last_sequence_number = sequence_number;

}

void recording_finalise() {
    uint8_t i;

    log_debug("Finalising recording channels");

    _recording_buffer_state_data_write();

    // Loop through channels
    for (uint32_t channel = 0; channel < n_recording_regions; channel++) {

        // If this channel's in use
        if (_has_been_initialsed(channel)) {
            recording_channel_t *recording_channel =
                &g_recording_channels[channel];

            // Calculate the number of bytes that have been written and write
            // back to SDRAM counter
            if (g_recording_channels[channel].missing_info)
                log_info(
                    "\tFinalising channel %u - dropped information while"
                    "buffering - state info stored in SDRAM", channel);
            else
                log_info(
                    "\tFinalising channel %u - state info stored in SDRAM",
                    channel);

            if (!_close_channel(channel)) {
                log_error("could not close channel %u.", channel);
            } else {
                log_info("closed channel %u.", channel);
            }
        }
    }
}

bool recording_initialize(
        address_t recording_data_address, uint32_t *recording_flags) {

    // Read in the parameters
    n_recording_regions = recording_data_address[N_REGIONS];
    uint8_t buffering_output_tag = recording_data_address[TAG];
    uint32_t buffering_destination = recording_data_address[TAG_DESTINATION];
    sdp_port = recording_data_address[SDP_PORT];
    buffer_size_before_trigger =
        recording_data_address[BUFFER_SIZE_BEFORE_REQUEST];
    time_between_triggers = recording_data_address[TIME_BETWEEN_TRIGGERS];
    if (time_between_triggers < MIN_TIME_BETWEEN_TRIGGERS) {
        time_between_triggers = MIN_TIME_BETWEEN_TRIGGERS;
    }
    last_sequence_number = &(recording_data_address[LAST_SEQUENCE_NUMBER]);

    log_info(
        "Recording %d regions, using output tag %d, size before trigger %d, "
        "time between triggers %d",
        n_recording_regions, buffering_output_tag, buffer_size_before_trigger,
        time_between_triggers);

    // Set up the space for holding recording pointers and sizes
    region_addresses = (address_t*) spin1_malloc(
        n_recording_regions * sizeof(address_t));
    if (region_addresses == NULL) {
        log_error("Not enough space to allocate recording addresses");
        return false;
    }
    region_sizes = (uint32_t *) spin1_malloc(
        n_recording_regions * sizeof(uint32_t));
    if (region_sizes == NULL) {
        log_error("Not enough space to allocate region sizes");
        return false;
    }

    // Set up the recording flags
    if (recording_flags != NULL) {
        *recording_flags = 0;
    }

    // Reserve the actual recording regions.
    // An extra sizeof(recording_channel_t) bytes are reserved per channel
    // to store the data after recording
    for (uint32_t counter = 0; counter < n_recording_regions; counter++) {
        uint32_t size = recording_data_address[
            REGION_POINTERS_START + n_recording_regions + counter];
        if (size > 0) {
            region_sizes[counter] = size;
            region_addresses[counter] = sark_xalloc(
                sv->sdram_heap, size + sizeof(recording_channel_t), 0,
                ALLOC_LOCK + ALLOC_ID + (sark_vec->app_id << 8));
            if (region_addresses[counter] == NULL) {
                log_error(
                    "Could not allocate recording region %u of %u bytes",
                    counter, size);
                return false;
            }
            recording_data_address[REGION_POINTERS_START + counter] =
                (uint32_t) region_addresses[counter];
            *recording_flags = (*recording_flags | (1 << counter));
        } else {
            recording_data_address[REGION_POINTERS_START + counter] = 0;
            region_addresses[counter] = 0;
            region_sizes[counter] = 0;
        }
    }
    g_recording_channels = (recording_channel_t*) sark_alloc(
        1, n_recording_regions * sizeof(recording_channel_t));
    if (!g_recording_channels) {
        log_error("Not enough space to create recording channels");
        return false;
    }
    log_debug("Allocated recording channels to 0x%08x", g_recording_channels);

    // Set up the channels and write the initial state data
    recording_reset();

    // Set up the buffer message
    req_hdr = (read_request_packet_header *) &(msg.cmd_rc);
    data_ptr = (read_request_packet_data *) &(req_hdr[1]);
    msg.flags = 0x7;
    msg.tag = buffering_output_tag;
    msg.dest_port = 0xFF;
    msg.srce_port = (sdp_port << 5) | spin1_get_core_id();
    msg.dest_addr = buffering_destination;
    msg.srce_addr = spin1_get_chip_id();

    return true;
}

void recording_reset() {

    // Go through the regions and set up the data
    for (uint32_t i = 0; i < n_recording_regions; i++) {
        uint32_t region_size = region_sizes[i];
        log_debug("region size %d", region_size);
        if (region_size > 0) {
            address_t region_address = region_addresses[i];

            log_debug("%d is size of buffer state in words",
                sizeof(recording_channel_t) / sizeof(address_t));

            address_t region_address_offset = &region_address[
                sizeof(recording_channel_t) / sizeof(address_t)];

            // store pointers to the start, current position and end of this
            g_recording_channels[i].start =
                (uint8_t*) region_address_offset;
            g_recording_channels[i].current_write =
                (uint8_t*) region_address_offset;
            g_recording_channels[i].current_read =
                (uint8_t*) region_address_offset;
            g_recording_channels[i].end =
                g_recording_channels[i].start + region_size;
            g_recording_channels[i].last_buffer_operation =
                BUFFER_OPERATION_READ;
            g_recording_channels[i].region_id = i;
            g_recording_channels[i].missing_info = 0;

            log_info(
                "Recording channel %u configured to use %u byte memory block"
                " starting at 0x%08x", i, region_size,
                g_recording_channels[i].start);

            simulation_sdp_callback_on(sdp_port, _buffering_in_handler);
        } else {
            g_recording_channels[i].start = NULL;
            g_recording_channels[i].current_write = NULL;
            g_recording_channels[i].current_read = NULL;
            g_recording_channels[i].end = NULL;
            g_recording_channels[i].last_buffer_operation =
                BUFFER_OPERATION_READ;
            g_recording_channels[i].region_id = i;
            g_recording_channels[i].missing_info = 0;

            log_info("Recording channel %u left uninitialised", i);
        }
    }
    _recording_buffer_state_data_write();
}

void recording_do_timestep_update(uint32_t time) {
    if (time - last_time_buffering_trigger > time_between_triggers) {
        _recording_send_buffering_out_trigger_message(0);
        last_time_buffering_trigger = time;
    }
}
