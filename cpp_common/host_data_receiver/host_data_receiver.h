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

static inline uint32_t get_word_from_buffer(
	std::vector<uint8_t> &buffer,
	uint32_t offset)
{
    // Explicit endianness
    uint32_t byte0 = buffer[offset + 0];
    uint32_t byte1 = buffer[offset + 1];
    uint32_t byte2 = buffer[offset + 2];
    uint32_t byte3 = buffer[offset + 3];
    return byte0 | (byte1 << 8) | (byte2 << 16) | (byte3 << 24);
}

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

class host_data_receiver {
    static constexpr uint32_t SEQUENCE_NUMBER_SIZE = 4;
    static constexpr uint32_t LAST_MESSAGE_FLAG_BIT_MASK = 0x80000000;
    static constexpr uint32_t SEQ_NUM_MASK = ~LAST_MESSAGE_FLAG_BIT_MASK;
public:
    static constexpr int SET_IP_TAG = 26;

    host_data_receiver(
	    int port_connection,
	    int placement_x,
	    int placement_y,
	    int placement_p,
	    const char *hostname,
	    int length_in_bytes,
	    int memory_address,
	    int chip_x,
	    int chip_y,
	    int iptag) :
	    port_connection(port_connection), placement_x(placement_x), placement_y(
		    placement_y), placement_p(placement_p), hostname(
		    hostname != nullptr ? hostname : ""), length_in_bytes(
		    (uint32_t) length_in_bytes), memory_address(
		    (uint32_t) memory_address), chip_x(chip_x), chip_y(
		    chip_y), iptag(iptag), buffer(length_in_bytes), started(
		    false), finished(false), miss_cnt(0)
    {
	rdr.thrown = false;
	pcr.thrown = false;
	max_seq_num = calculate_max_seq_num();
	print_debug_messages = (std::getenv("DEBUG_RETRANSMIT") != nullptr);
    }
    const uint8_t *get_data();
    void get_data_threadable(
	    const char *filepath_read,
	    const char *filepath_missing);
#ifdef PYBIND11_MODULE
    pybind11::bytes get_data_for_python(
	    char *hostname, int port_connection, int placement_x,
	    int placement_y, int placement_p, int length_in_bytes,
	    int memory_address, int chip_x, int chip_y, int iptag);
#endif

private:
    void send_initial_command(
	    const UDPConnection &control,
	    const UDPConnection &data_flow) const;
    void receive_message(
	    const UDPConnection &receiver,
	    std::vector<uint8_t> &buffer) const;
    bool retransmit_missing_sequences(
	    const UDPConnection &sender,
	    const std::set<uint32_t> &received_seq_nums);
    uint32_t calculate_max_seq_num() const;
    uint32_t calculate_offset(uint32_t seq_num) const;
    bool check(
	    const std::set<uint32_t> &received_seq_nums,
	    uint32_t max_needed) const;
    void process_data(
	    const UDPConnection &sender,
	    bool &finished,
	    std::set<uint32_t> &received_seq_nums,
	    std::vector<uint8_t> &recvdata)
    {
	uint32_t first_packet_element = get_word_from_buffer(recvdata, 0);
	uint32_t content_length = recvdata.size() - SEQUENCE_NUMBER_SIZE;
	const uint8_t *content_bytes = recvdata.data() + SEQUENCE_NUMBER_SIZE;

	// Unpack the first word
	uint32_t seq_num = first_packet_element & SEQ_NUM_MASK;
	bool is_end_of_stream = (first_packet_element
		& LAST_MESSAGE_FLAG_BIT_MASK) != 0;
	finished |= process_data(sender, received_seq_nums, is_end_of_stream,
		seq_num, content_length, content_bytes);
    }
    bool process_data(
	    const UDPConnection &sender,
	    std::set<uint32_t> &received_seq_nums,
	    bool is_end_of_stream,
	    uint32_t seq_num,
	    uint32_t content_length,
	    const uint8_t *content_bytes);
    void reader_thread(const UDPConnection &receiver);
    void processor_thread(const UDPConnection &sender);

    //Used to verify if one of the thread threw any exception
    struct thexc {
	const char *val;
	volatile bool thrown;
    };

    const int port_connection;
    const int placement_x;
    const int placement_y;
    const int placement_p;
    const std::string hostname;
    const uint32_t length_in_bytes;
    const uint32_t memory_address;
    const int chip_x;
    const int chip_y;
    const int iptag;
    PQueue<std::vector<uint8_t>> messqueue;
    std::vector<uint8_t> buffer;
    uint32_t max_seq_num;
    thexc rdr, pcr;
    bool started, finished;
    int miss_cnt;
    bool print_debug_messages;
};

#endif
