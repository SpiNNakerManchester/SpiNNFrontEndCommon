#ifndef _HOST_DATA_RECEIVER_
#define _HOST_DATA_RECEIVER_

#include <string>
#include <unistd.h>
#include <iostream>
#include <algorithm>
#include <vector>
#include <set>
#include <ctime>
#include <cstdint>
#include <thread>
#include <cstdlib>

#if 0
#include <pybind11/pybind11.h>
#endif

#include <UDPConnection.h>
#include "PQueue.h"

/// Convert a word read from SpiNNaker and convert to host endianness.
static inline uint32_t get_word_from_buffer(
	const std::vector<uint8_t> &buffer, ///< [in] buffer to read from
	uint32_t offset) ///< [in] index into the buffer to start at
{
    // Explicit endianness
    uint32_t byte0 = buffer[offset + 0];
    uint32_t byte1 = buffer[offset + 1];
    uint32_t byte2 = buffer[offset + 2];
    uint32_t byte3 = buffer[offset + 3];
    return byte0 | (byte1 << 8) | (byte2 << 16) | (byte3 << 24);
}

/// Convert a word from host endianness into SpiNNaker endianness.
///
/// The word is returned so it can be stored in an array of words for
/// marshaling purposes.
static inline uint32_t make_word_for_buffer(uint32_t word)
{
    // Explicit endianness
    union {
	struct {
	    uint8_t byte0, byte1, byte2, byte3;
	};
	uint32_t word;
    } converter;
    converter.byte0 = (word >> 0) & 0xFF;
    converter.byte1 = (word >> 8) & 0xFF;
    converter.byte2 = (word >> 16) & 0xFF;
    converter.byte3 = (word >> 24) & 0xFF;
    return converter.word;
}

/// The class that moves data from SpiNNaker to the host.
///
/// This works by redirecting the given IPTag to point to a UDP port under
/// the control of this class, and then uses the SpiNNaker Fixed Route
/// Outbound Data Streaming Protocol to move the data. It relies on the
/// SpiNNaker system to already be configured correctly.
class host_data_receiver {
    /// Number of bytes in a sequence number.
    static constexpr uint32_t SEQUENCE_NUMBER_SIZE = 4;

    /// Mask used to extract the last-message flag from the sequence number
    /// field.
    static constexpr uint32_t LAST_MESSAGE_FLAG_BIT_MASK = 0x80000000;

    /// Mask used to extract the actual sequence number from the sequence
    /// number field.
    static constexpr uint32_t SEQ_NUM_MASK = ~LAST_MESSAGE_FLAG_BIT_MASK;

    /// Maximum size of SDP message.
    ///
    /// Constraint due to SC&MP.
    static constexpr int MAX_SDP_PACKET_LENGTH = 280;

public:
    /// The code for the "Set IPTag" command.
    static constexpr int SET_IP_TAG = 26;

    /// Initialise the class's instance.
    ///
    /// Note that the arguments are NOT checked for correctness, and enough
    /// memory must be available for the data being retrieved.
    host_data_receiver(int port_connection, ///< [in] What UDP port on SpiNNaker to talk to
	    int placement_x,       ///< [in] The chip to read from (X coord)
	    int placement_y,       ///< [in] The chip to read from (Y coord)
	    int placement_p,       ///< [in] The chip to read from (P coord)
	    std::string hostname, ///< [in] The hostname of the SpiNNaker board
	    int length_in_bytes,   ///< [in] How many bytes to read
	    int memory_address,    ///< [in] Where in memory to read from
	    int chip_x,            ///< [in] X coord for IPTag
	    int chip_y,            ///< [in] Y coord for IPTag
	    int iptag)             ///< [id] ID of the IPTag to set/update
    :
	    port_connection(port_connection), placement_x(placement_x), placement_y(
		    placement_y), placement_p(placement_p), hostname(
		    hostname), length_in_bytes((uint32_t) length_in_bytes), memory_address(
		    (uint32_t) memory_address), chip_x(chip_x), chip_y(
		    chip_y), iptag(iptag), buffer(length_in_bytes), received_count(0),
		    started(false), finished(false), miss_cnt(0)
    {
	rdr.thrown = false;
	pcr.thrown = false;
	max_seq_num = calculate_max_seq_num();
	received_seq_nums = std::vector<bool>(max_seq_num);
	print_debug_messages = (std::getenv("DEBUG_RETRANSMIT") != nullptr);
    }

    /// Get the data from the machine.
    ///
    /// This creates two threads to manage the servicing of the UDP port, and
    /// the assembly of the results and generation of reinjection packets.
    /// Calling this method repeatedly will only transfer the data block once
    /// provided the first transfer has completed.
    const uint8_t *get_data();

    /// Get the data from the machine and write it to the given file.
    ///
    /// Also writes a summary of any reinjection activity to the other file.
    /// \param filepath_read [in] Name of file to write data to
    /// \param filepath_missing [in] Name of file to write report to; nullable
    void get_data_threadable(
	    std::string &filepath_read,
	    std::string &filepath_missing);

#ifdef PYBIND11_MODULE
    /// Special version of get_data that includes Python datatype adapters.
    pybind11::object get_data_for_python();
#endif

    /// Return the number of missing data packets in the data stream,
    /// including across all reinjections.
    int get_missing_data_count() const {
	return miss_cnt;
    }

private:
    /// Start the data transfer.
    /// \param control [in] Where to talk to.
    /// \param data_flow [in] Where to direct data traffic to.
    void send_initial_command(
	    const UDPConnection &control,
	    const UDPConnection &data_flow) const;

    /// Receive a SpiNNaker message over UDP.
    /// \param receiver [in] Where to get a message from.
    /// \param working_buffer [out] Where to store the message.
    void receive_message(
	    const UDPConnection &receiver,
	    std::vector<uint8_t> &working_buffer) const
    {
	working_buffer.resize(MAX_SDP_PACKET_LENGTH);
	receiver.receive_data(working_buffer);
    }

    /// Send those messages.
    /// \param sender [in] Where to send to.
    /// \param received_seq_nums [in] Which sequence numbers have been received.
    bool retransmit_missing_sequences(
	    const UDPConnection &sender);

    /// Get the maximum sequence number for this transfer.
    uint32_t calculate_max_seq_num() const;

    /// Get the offset into the main buffer for this block.
    /// \param seq_num [in] The sequence number of the block.
    uint32_t calculate_offset(uint32_t seq_num) const;

    /// Has all the data been transferred?
    bool check() const;

    /// Process a received message.
    /// \param sender [in] Where to send reinjection messages if needed.
    /// \param finished [in,out] Whether the data processing is done.
    /// \param received_seq_nums [in,out] Which sequence numbers have been received.
    /// \param recvdata [in] The content of the received message
    void process_data(
	    const UDPConnection &sender,
	    bool &finished,
	    const std::vector<uint8_t> &recvdata)
    {
	uint32_t first_packet_element = get_word_from_buffer(recvdata, 0);
	uint32_t content_length = recvdata.size() - SEQUENCE_NUMBER_SIZE;
	const uint8_t *content_bytes = recvdata.data() + SEQUENCE_NUMBER_SIZE;

	// Unpack the first word
	uint32_t seq_num = first_packet_element & SEQ_NUM_MASK;
	bool is_end_of_stream = (first_packet_element
		& LAST_MESSAGE_FLAG_BIT_MASK) != 0;
	finished |= process_data(sender, is_end_of_stream, seq_num,
		content_length, content_bytes);
    }

    /// Process a received message.
    /// \param sender [in] Where to send reinjection messages if needed.
    /// \param received_seq_nums [in,out] Which sequence numbers have been received.
    /// \param is_end_of_stream [in] Whether this is the last message in a stream.
    /// \param seq_num [in] The sequence number of the message.
    /// \param content_length [in] The number of bytes in the content.
    /// \param content_bytes [in] The bytes of content of the message.
    bool process_data(
	    const UDPConnection &sender,
	    bool is_end_of_stream,
	    uint32_t seq_num,
	    uint32_t content_length,
	    const uint8_t *content_bytes);

    /// The implementation of the thread that receives messages from SpiNNaker.
    /// \param receiver [in] Where to receive data from.
    void reader_thread(const UDPConnection &receiver);

    /// The implementation of the thread that receives messages from SpiNNaker.
    /// \param sender [in] Where to send reinjection requests to.
    void processor_thread(const UDPConnection &sender);

    /// Used to verify if one of the thread threw any exception
    struct thexc {
	const char *val;      ///< The message of the exception
	volatile bool thrown; ///< If an exception was thrown
    };

    /// What UDP port on SpiNNaker to talk to
    const int port_connection;
    /// The chip to read from (X coord)
    const int placement_x;
    /// The chip to read from (Y coord)
    const int placement_y;
    /// The chip to read from (P coord)
    const int placement_p;
    /// The name of the SpiNNaker system
    const std::string hostname;
    /// Number of bytes to read from SpiNNaker CPU
    const uint32_t length_in_bytes;
    /// Where on the SpiNNaker CPU those bytes
    const uint32_t memory_address;
    /// X coord for IPTag
    const int chip_x;
    /// Y coord for IPTag
    const int chip_y;
    /// ID of the IPTag to set/update
    const int iptag;
    /// Transfers messages from reader thread to processor thread
    PQueue<std::vector<uint8_t>> messqueue;
    /// Where data is accumulated after being read
    std::vector<uint8_t> buffer;
    /// Collection of bits saying whether a sequence number has arrived
    std::vector<bool> received_seq_nums;
    /// The maximum expected sequence number
    uint32_t max_seq_num;
    /// How many unique sequence numbers have been received
    uint32_t received_count;
    /// Exception reporting for reader thread
    thexc rdr;
    /// Exception reporting for processor thread
    thexc pcr;
    /// Has the transfer started?
    bool started;
    /// Has the transfer completed?
    bool finished;
    /// How many packets have been requested to be reinjected?
    int miss_cnt;
    /// Whether we should print debugging messages
    bool print_debug_messages;
};

#endif
