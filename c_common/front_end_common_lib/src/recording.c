/*! \file
 *
 *  \brief implementation of recording.h
 *
 */

#include <recording.h>
#include <buffered_eieio_defs.h>
#include <data_specification.h>

// Standard includes
#include <string.h>
#include <debug.h>

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

//! positions within the recording region definition for each type of event
//! Available to be recorded
/*
typedef enum recording_positions {
    flags_for_recording, spikes_position, protential_position, gsyn_position,
} recording_positions;
*/


//---------------------------------------
// Globals
//---------------------------------------
//! array containing all possible channels.
static recording_channel_t *g_recording_channels;
static uint32_t n_recording_regions = 0;
static uint8_t buffering_output_tag;
static uint32_t buffering_out_fsm = 0;
static uint8_t buffering_out_state_region = 0;

//---------------------------------------
// Private method
//---------------------------------------
//! \brief checks that a channel has been initialised or is still awaiting
//! initialisation
//! \param[in] channel the channel strut which represents the memory data for a
//! given recording region
//! \return boolean which is True if the channel has been initialised or false
//! otherwise
static inline bool has_been_initialsed(uint8_t channel) {
    return (g_recording_channels[channel].start != NULL
            && g_recording_channels[channel].end != NULL);
}

//----------------------------------------
//  Private method
//----------------------------------------
//! \brief closes a channel so that future records fail as the channel has
//! been closed
//! \param[in] channel the channel strut which represents the memory data for a
//! given recording region, which is to be closed.
//! \return boolean which is True is the channel was successfully closed and
//! False otherwise.
static inline bool close_channel(uint8_t channel) {
    g_recording_channels[channel].start = NULL;
    g_recording_channels[channel].end = NULL;
    return true;
}

static void buffering_in_handler(uint mailbox, uint port)
{
    use(port);
    sdp_msg_t *msg = (sdp_msg_t *) mailbox;
    uint16_t length = msg -> length;
    eieio_msg_t eieio_msg_ptr = (eieio_msg_t) &(msg -> cmd_rc);

    recording_eieio_packet_handler(eieio_msg_ptr, length - 8);

    spin1_msg_free(msg);
}

//this is equivalent to the one in reverse_iptag_multicast_source
static uint32_t compute_available_space_in_channel(uint8_t channel)
{
    uint8_t *buffer_region = g_recording_channels[channel].start;
    uint8_t *end_of_buffer_region = g_recording_channels[channel].end ;
    uint8_t *write_pointer = g_recording_channels[channel].current_write;
    uint8_t *read_pointer = g_recording_channels[channel].current_read;
    buffered_operations last_buffer_operation =
                    g_recording_channels[channel].last_buffer_operation;

    if (read_pointer < write_pointer) {
        uint32_t final_space = (uint32_t) end_of_buffer_region -
                               (uint32_t) write_pointer;
        uint32_t initial_space = (uint32_t) read_pointer -
                                 (uint32_t) buffer_region;
        return final_space + initial_space;
    } else if (write_pointer < read_pointer) {
        return (uint32_t) read_pointer - (uint32_t) write_pointer;
    } else if (last_buffer_operation == BUFFER_OPERATION_WRITE) {

        // If pointers are equal, buffer is full if last op is write
        return 0;
    } else {

        // If pointers are equal, buffer is empty if last op is read
        return (end_of_buffer_region - buffer_region);
    }
}

//---------------------------------------
// Public API
//---------------------------------------
//! \extracts the sizes of the recorded regions from SDRAM
//! \param[in] region_start the absolute address in SDRAM
//! \param[in] recording_flags the flag ids read from SDRAM
//! \param[out] spike_history_region_size if this region is set to have
//! data recorded into it, it will get set with the size of the spike
//! recorder region
//! \param[out] neuron_potential_region_size if this region is set to have
//! data recorded into it, it will get set with the size of the potential
//! recorder region
//! \param[out] neuron_gysn_region_size
//! \return This method does not return anything
/*
recording_read_region_sizes(address_t start_address, uint32_t n_regions, uint32_t **array_to_read_into)
void recording_read_region_sizes(
        address_t region_start, uint32_t* recording_flags,
        uint32_t* spike_history_region_size,
        uint32_t* neuron_potential_region_size,
        uint32_t* neuron_gysn_region_size) {
    *recording_flags = region_start[flags_for_recording];
    if (recording_is_channel_enabled(*recording_flags,
                e_recording_channel_spike_history)
            && (spike_history_region_size != NULL)) {
        *spike_history_region_size = region_start[spikes_position];
    }
    if (recording_is_channel_enabled(*recording_flags,
                e_recording_channel_neuron_potential)
            && (neuron_potential_region_size != NULL)) {
        *neuron_potential_region_size = region_start[protential_position];
    }
    if (recording_is_channel_enabled(*recording_flags,
                e_recording_channel_neuron_gsyn)
            && (neuron_gysn_region_size != NULL)) {
        *neuron_gysn_region_size = region_start[gsyn_position];
    }
}
*/

//! \brief initialises a channel with the start, end, size and current position
//! in SDRAM for the channel handed in.
//! \param[in] output_region the absolute memory address in SDRAM for the
//!recording region
//! \param[out] channel the channel to which we are initialising the
//! parameters of.
// \param[out] size_bytes the size of memory that the channel can put data into
//! \return boolean which is True if the channel was successfully initialised
//! or False otherwise.

/*
bool recording_initialise_channel(
        address_t output_region, uint8_t channel,
        uint32_t size_bytes) {

    log_info("size inside record is %u", size_bytes);

    if (has_been_initialsed(channel)) {
        log_error("Recording channel %u already configured", channel);

        // CHANNEL already initialised
        return false;
    } else {
        recording_channel_t *recording_channel = &g_recording_channels[channel];

        // Calculate pointers to the start, current position and end of this
        // memory block
        recording_channel->start = (uint8_t*) output_region;
        recording_channel->current_write = (uint8_t*) output_region;
        recording_channel->current_read = (uint8_t*) output_region;
        recording_channel->end = recording_channel->start + size_bytes;
        recording_channel->last_buffer_operation = BUFFER_OPERATION_READ;
        recording_channel->region_id = // this needs to be passed from caller

        log_info("Recording channel %u configured to use %u byte memory block"
                 " starting at %08x",
                 channel, size_bytes, recording_channel->start);
        return true;
    }
}
*/

//! \brief records some data into a specific recording channel.
//! \param[in] channel the channel to store the data into.
//! \param[in] data the data to store into the channel.
//! \param[in] size_bytes the number of bytes that this data will take up.
//! \return boolean which is True if the data has been stored in the channel,
//! False otherwise.
bool recording_record(
        uint8_t channel, void *data, uint32_t size_bytes) {
    if (has_been_initialsed(channel)) {
        recording_channel_t *recording_channel = &g_recording_channels[channel];

        //uint32_t recording_space = recording_channel->end - recording_channel->start;
        uint32_t space_available = compute_available_space_in_channel(channel);

        // If there's space to record
        if (space_available >= size_bytes) {

            // Copy data into recording channel
            recording_write_memory(channel, data, size_bytes);

            //trigger buffering_out_mechanism - if needed
            //TODO: This may be needed here, although in this position there may be multiple messages sent
            // one for each recording channel - to be though of...

            //recording_send_buffering_out_trigger_message(0);

            return true;
        } else {
            if (!g_recording_channels[channel].missing_info)
            {
                log_info("ERROR: recording channel %u out of space", channel);
                g_recording_channels[channel].missing_info = 1;
            }
            return false;
        }
    } else {
        return false;
    }

}

//! \brief updated the first word in the recording channel's memory region with
//! the number of bytes that was actually written to SDRAM and then closes the
//! channel so that future records fail.
//! \return nothing
void recording_finalise() {
    uint8_t i;

    log_info("Finalising recording channels");

    // Get the address this core's DTCM data starts at from SRAM
    address_t address = data_specification_get_data_address();

    // Get the region address store channel details
    address_t buffering_out_control_reg = data_specification_get_region(
        buffering_out_state_region, address);
    address_t out_ptr = buffering_out_control_reg;

    log_info("Storing channel state info in region %d starting at 0x%08x", buffering_out_state_region, out_ptr);
//    log_info("data spec address: 0x%08x, state region id: %d, state_region_address: 0x%08x", (uint32_t)
//address, buffering_out_state_region, (uint32_t) out_ptr);

    // store number of recording regions
    spin1_memcpy(out_ptr, &n_recording_regions, sizeof(n_recording_regions));
    out_ptr++;

    // store info related to the state of the transmission to avoid possible
    // duplication of info on the host side
    spin1_memcpy(out_ptr, &buffering_out_fsm, sizeof(buffering_out_fsm));
    out_ptr++;

    // store info on the channel status so that the host can flush the info
    // buffered in SDRAM
    spin1_memcpy(out_ptr, g_recording_channels, sizeof(recording_channel_t) * n_recording_regions);

    // Loop through channels
    for (uint32_t channel = 0; channel < n_recording_regions; channel++) {
        // If this channel's in use
        if (has_been_initialsed(channel)) {
            recording_channel_t *recording_channel =
                &g_recording_channels[channel];

            // Calculate the number of bytes that have been written and write
            // back to SDRAM counter
            if (g_recording_channels[channel].missing_info)
                log_info("\tFinalising channel %u - dropped information while buffering - state info stored in SDRAM", channel);
            else
                log_info("\tFinalising channel %u - state info stored in SDRAM", channel);

            if(!close_channel(channel)){
                log_error("could not close channel %u.", channel);
            }
            else{
                log_info("closed channel %u.", channel);
            }
        }
//        else{
//            log_error("channel %u is already closed.", channel);
//        }
    }
}

bool recording_initialize(uint8_t n_regions, uint8_t *region_ids,
                          uint32_t* region_sizes, uint8_t state_region,
                          uint8_t tag_id, uint32_t *recording_flags)
{
    uint32_t i;

    // if already initialised, don't re-initialise
    if (!n_recording_regions && n_regions <= 0)
        return false;

    if (recording_flags)
        *recording_flags = 0;

    n_recording_regions = n_regions;
    buffering_out_state_region = state_region;
    buffering_output_tag = tag_id;

    g_recording_channels = (recording_channel_t*) spin1_malloc(n_recording_regions * sizeof(recording_channel_t));
    if (!g_recording_channels)
        return false;

    address_t address = data_specification_get_data_address();

    for (i = 0; i < n_regions; i++)
    {
        if (region_sizes[i] > 0)
        {
            address_t region_address = data_specification_get_region(region_ids[i], address);

            // store pointers to the start, current position and end of this
            g_recording_channels[i].start = (uint8_t*) region_address;
            g_recording_channels[i].current_write = (uint8_t*) region_address;
            g_recording_channels[i].current_read = (uint8_t*) region_address;
            g_recording_channels[i].end = g_recording_channels[i].start + region_sizes[i];
            g_recording_channels[i].last_buffer_operation = BUFFER_OPERATION_READ;
            g_recording_channels[i].region_id = region_ids[i];
            g_recording_channels[i].missing_info = 0;

            *recording_flags = (*recording_flags | (1 << i));

            log_info("Recording channel %u configured to use %u byte memory block"
                     " starting at 0x%08x",
                     i, region_sizes[i], g_recording_channels[i].start);

            // priority of this callback may need to be the same as time interrupt
            // it is a producer/consumer paradigm, where the producer is the timer callback
            // the consumer is this routine and the two need to operate in mutual
            // exclusion on the state variables
            spin1_sdp_callback_on(BUFFERING_OUT_SDP_PORT, buffering_in_handler, 2);
         }
         else
         {
            g_recording_channels[i].start = NULL;
            g_recording_channels[i].current_write = NULL;
            g_recording_channels[i].current_read = NULL;
            g_recording_channels[i].end = NULL;
            g_recording_channels[i].last_buffer_operation = BUFFER_OPERATION_READ;
            g_recording_channels[i].region_id = region_ids[i];
            g_recording_channels[i].missing_info = 0;

            log_info("Recording channel %u left uninitialised", i);
         }
    }
    return true;
}

//this is equivalent to add_eieio_packet_to_sdram
bool recording_write_memory(
        uint8_t channel, void *data, uint32_t length)
{
    uint8_t *buffer_region = g_recording_channels[channel].start;
    uint8_t *end_of_buffer_region = g_recording_channels[channel].end ;
    uint8_t *write_pointer = g_recording_channels[channel].current_write;
    uint8_t *read_pointer = g_recording_channels[channel].current_read;
    buffered_operations last_buffer_operation =
                    g_recording_channels[channel].last_buffer_operation;

/*
    io_printf (IO_BUF, "ch = %d, start = 0x%08x, read = 0x%08x, write = 0x%08x, "
          "end = 0x%08x, last_buffer_operation == read = %d, data len = %d\n",
          channel, buffer_region, read_pointer,  write_pointer, end_of_buffer_region,
          last_buffer_operation == BUFFER_OPERATION_READ, length);
*/

    if ((read_pointer < write_pointer) ||
            (read_pointer == write_pointer &&
                last_buffer_operation == BUFFER_OPERATION_READ)) {
        uint32_t final_space = (uint32_t) end_of_buffer_region -
                               (uint32_t) write_pointer;

        if (final_space >= length) {
//            log_debug("Packet fits in final space of %d", final_space);

            spin1_memcpy(write_pointer, data, length);
            write_pointer += length;
            if (write_pointer >= end_of_buffer_region) {
                write_pointer = buffer_region;
//                io_printf(IO_BUF, "channel %d, write wrap around\n", channel);
            }
            g_recording_channels[channel].current_write = write_pointer;
            g_recording_channels[channel].last_buffer_operation = BUFFER_OPERATION_WRITE;
            return true;
        } else {

            uint32_t total_space = final_space + ((uint32_t) read_pointer -
                                                  (uint32_t) buffer_region);
            if (total_space < length) {
//                log_debug("Not enough space in final area (%d bytes)", total_space);
//                io_printf(IO_BUF, "Not enough space in final area (%d bytes)", total_space);
                return false;
            }

//            log_debug("Copying first %d bytes to final space of %d", final_space);
            spin1_memcpy(write_pointer, data, final_space);
            write_pointer = buffer_region;
            data += final_space;

            uint32_t final_len = length - final_space;
//            log_debug("Copying remaining %d bytes", final_len);
            spin1_memcpy(write_pointer, data, final_len);
            write_pointer += final_len;
            if (write_pointer == end_of_buffer_region) {
                write_pointer = buffer_region;
//                io_printf(IO_BUF, "channel %d, write wrap around\n", channel);
            }
            g_recording_channels[channel].current_write = write_pointer;
            g_recording_channels[channel].last_buffer_operation = BUFFER_OPERATION_WRITE;
            return true;
        }
    } else if (write_pointer < read_pointer) {
        uint32_t middle_space = (uint32_t) read_pointer -
                                (uint32_t) write_pointer;

        if (middle_space < length) {
//            log_debug("Not enough space in middle (%d bytes)", middle_space);
//            io_printf(IO_BUF, "Not enough space in middle (%d bytes)\n", middle_space);
            return false;
        } else {
//            log_debug("Packet fits in middle space of %d", middle_space);
            spin1_memcpy(write_pointer, data, length);
            write_pointer += length;
            if (write_pointer == end_of_buffer_region) {
                write_pointer = buffer_region;
//                io_printf(IO_BUF, "channel %d, write wrap around\n", channel);
            }
            g_recording_channels[channel].current_write = write_pointer;
            g_recording_channels[channel].last_buffer_operation = BUFFER_OPERATION_WRITE;
            return true;
        }
    }

//    log_debug("Buffer already full");
//    io_printf(IO_BUF, "Buffer already full");
    return false;

}

void recording_send_buffering_out_trigger_message(bool flush_all)
{
    uint channel;
    sdp_msg_t msg;
    read_request_packet_header *req_hdr = (read_request_packet_header *) &(msg.cmd_rc);
    read_request_packet_data *data_ptr = (read_request_packet_data *) &(req_hdr[1]);
    uint msg_size = 16 + sizeof(read_request_packet_header);
    uint n_requests = 0;

    for (channel = 0; channel < n_recording_regions; channel++)
    {
        uint32_t channel_space_total = (uint32_t)
            (g_recording_channels[channel].end - g_recording_channels[channel].start);
        uint32_t channel_space_available = compute_available_space_in_channel(channel);

        if (has_been_initialsed(channel) &&
           (flush_all || channel_space_total - channel_space_available >= MIN_BUFFERING_OUT_LIMIT))
        {
            uint8_t *buffer_region = g_recording_channels[channel].start;
            uint8_t *end_of_buffer_region = g_recording_channels[channel].end ;
            uint8_t *write_pointer = g_recording_channels[channel].current_write;
            uint8_t *read_pointer = g_recording_channels[channel].current_read;
            buffered_operations last_buffer_operation =
                    g_recording_channels[channel].last_buffer_operation;

            if (read_pointer < write_pointer)
            {
                data_ptr[n_requests].processor_and_request = 0;
                data_ptr[n_requests].sequence = 0;
                data_ptr[n_requests].channel = channel;
                data_ptr[n_requests].region = g_recording_channels[channel].region_id;
                data_ptr[n_requests].start_address = (uint32_t) read_pointer;
                data_ptr[n_requests].space_to_be_read = (write_pointer - read_pointer);
                n_requests++;
            }
            else if ((write_pointer < read_pointer) ||
                     (write_pointer == read_pointer && last_buffer_operation == BUFFER_OPERATION_WRITE))
            {
                data_ptr[n_requests].processor_and_request = 0;
                data_ptr[n_requests].sequence = 0;
                data_ptr[n_requests].channel = channel;
                data_ptr[n_requests].region = g_recording_channels[channel].region_id;
                data_ptr[n_requests].start_address = (uint32_t) read_pointer;
                data_ptr[n_requests].space_to_be_read = (end_of_buffer_region - read_pointer);
                n_requests++;

                data_ptr[n_requests].processor_and_request = 0;
                data_ptr[n_requests].sequence = 0;
                data_ptr[n_requests].channel = channel;
                data_ptr[n_requests].region = g_recording_channels[channel].region_id;
                data_ptr[n_requests].start_address = (uint32_t) buffer_region;
                data_ptr[n_requests].space_to_be_read = (write_pointer - buffer_region);
                n_requests++;
            }
            else
            {
                // something somewhere went terribly wrong,
                // this should never happen
                log_debug("Unknown channel state - channel: %d, start pointer: %d, end pointer: %d, read_pointer: %d, write_pointer: %d, last operation==READ: %d\n", channel, buffer_region, end_of_buffer_region, read_pointer, write_pointer, last_buffer_operation==BUFFER_OPERATION_READ);
            }
        }
    }

    if (n_requests > 0)
    {
        req_hdr -> eieio_header_command = 0x4008; // eieio command packet with command ID 8
        req_hdr -> chip_id = spin1_get_chip_id();
        data_ptr[0].processor_and_request = (spin1_get_core_id() << 3) | n_requests;
        //buffering_out_fsm = (buffering_out_fsm + 1) & MAX_SEQUENCE_NO;
        data_ptr[0].sequence = buffering_out_fsm;
        msg_size += (n_requests * sizeof(read_request_packet_data));
        msg.length = msg_size;
        msg.flags = 0x7;
        msg.tag = buffering_output_tag;
        msg.dest_port = 0xFF;
        msg.srce_port = (BUFFERING_OUT_SDP_PORT << 5) | spin1_get_core_id();
        msg.dest_addr = 0;
        msg.srce_addr = spin1_get_chip_id();

        spin1_send_sdp_msg (&msg, 1);

/*
        io_printf(IO_BUF, "number of requests: %d, packet length: %d\n", n_requests, msg.length);

        unsigned char *print_ptr = &msg;
        for (uint i = 0; i < msg.length; i++)
        {
          io_printf(IO_BUF, "%02x ", print_ptr[i]);
          if ((i & 0xF) == 0xF)
            io_printf(IO_BUF, "\n");
        }
        io_printf(IO_BUF, "\n");
*/
    }
}

void recording_eieio_packet_handler(eieio_msg_t msg, uint length)
{
    uint16_t data_hdr_value = msg[0];
    uint8_t pkt_type = (data_hdr_value >> 14) && 0x03;
    uint16_t pkt_command = data_hdr_value & (~0xC000);

    if (pkt_type == 0x01)
    {
//        log_debug("recording - parsing a command packet");
        switch (pkt_command) {
        case HOST_DATA_READ:
//            log_debug("command: HOST_DATA_READ");
            recording_host_data_read(msg, length);
            break;

        default:
            log_debug("unhandled command id %d", pkt_command);
            break;
        }
    }
}

void recording_host_data_read(eieio_msg_t msg, uint length)
{
    host_data_read_packet_header *ptr_hdr = (host_data_read_packet_header *) msg;
    host_data_read_packet_data *ptr_data = (host_data_read_packet_data *) (&ptr_hdr[1]);

    uint8_t n_requests = ptr_hdr -> request;
    uint8_t sequence = ptr_hdr -> sequence;

    uint32_t i;

    if (sequence != buffering_out_fsm)
    {
//        log_debug("dropping packet with sequence no: %d", sequence);
        return;
    }
    buffering_out_fsm = (buffering_out_fsm + 1) & MAX_SEQUENCE_NO;

    for (i = 0; i < n_requests; i++)
    {
        uint8_t channel = ptr_data[i].channel;
        uint32_t space_read = ptr_data[i].space_read;

        uint32_t temp_value = (uint32_t) (g_recording_channels[channel].current_read + space_read);

//        io_printf(IO_BUF, "channel %d, updating read pointer by %d bytes, from 0x%08x to ", channel, space_read, g_recording_channels[channel].current_read);
        if (temp_value >= (uint32_t) g_recording_channels[channel].end)
        {
            uint32_t channel_space_total = (uint32_t)
                (g_recording_channels[channel].end - g_recording_channels[channel].start);
            temp_value = temp_value - channel_space_total;
//            io_printf(IO_BUF, "channel %d, read wrap around\n", channel);
        }

        g_recording_channels[channel].current_read = (uint8_t *) temp_value;
        g_recording_channels[channel].last_buffer_operation = BUFFER_OPERATION_READ;

//        io_printf(IO_BUF, "0x%08x\n", temp_value);
    }
}
