#include <cstdint>
#include "host_data_receiver.h"
#include "Messages.h"
#include <vector>
#include <cassert>
#include <chrono>
#include <fstream>
#include <cstdlib>

using namespace std;
using namespace std::literals::chrono_literals; // BLACK MAGIC!

/// The usual port for SDP
static constexpr int SDP_PORT = 17893;

// time out constants
/// How long between reinjection request packets?
static constexpr auto DELAY_PER_SENDING = 10ms;
/// How many timeouts will we tolerate?
static constexpr uint32_t TIMEOUT_RETRY_LIMIT = 20;

// consts for data and converting between words and bytes
/// Number of words to put in a packet apart from the sequence number
static constexpr uint32_t WORDS_PER_PACKET_WITH_SEQUENCE_NUM = WORDS_PER_PACKET - 1;
/// Number of bytes per SpiNNaker word
static constexpr uint32_t WORD_TO_BYTE_CONVERTER = 4;
/// Number of bytes of payload in a normal data packet
static constexpr uint32_t NORMAL_PAYLOAD_LENGTH =
	WORDS_PER_PACKET_WITH_SEQUENCE_NUM * WORD_TO_BYTE_CONVERTER;
/// Required size of receiver buffer to handle all SpiNNaker messages
static constexpr uint32_t RECEIVE_BUFFER_LENGTH = WORDS_PER_PACKET * WORD_TO_BYTE_CONVERTER;

/// Division that rounds up
static inline uint32_t ceildiv(uint32_t numerator, uint32_t denominator)
{
    auto result = std::div(static_cast<int32_t>(numerator), denominator);
    return result.quot + (result.rem > 0);
}

//Function for asking data to the SpiNNaker system
void host_data_receiver::send_initial_command(
	const UDPConnection<BlockAlloc> &control,
	const UDPConnection<BlockAlloc> &data_flow) const
{
    //Build an SCP request to set up the IP Tag associated to this socket
    const SetIPTagMessage set_iptag_req(chip_x, chip_y, iptag,
	    data_flow.get_local_ip(), data_flow.get_local_port());

    //Send SCP request and receive (and ignore) response
    control.send_message(set_iptag_req);

    buffer_t working_buffer;
    receive_message(control, working_buffer);

    // Create Data request SDP packet
    const StartSendingMessage message(placement_x, placement_y, placement_p,
	    port_connection, memory_address, length_in_bytes);
    //send message
    control.send_message(message);
}

// Function for asking for retransmission of missing sequences
bool host_data_receiver::retransmit_missing_sequences(
	const UDPConnection<BlockAlloc> &sender)
{
    //Calculate number of missing sequences based on difference between
    //expected and received
    vector<uint32_t> missing_seq(0);
    // We know how many elements we expect to be missing
    missing_seq.reserve(max_seq_num - received_count);
    if (print_debug_messages && missing_seq.capacity()) {
	cerr << "missing sequence numbers: {";
    }

    // Calculate missing sequence numbers and add them to "missing"
    for (uint32_t i = 0; i < max_seq_num ; i++) {
	if (!received_seq_nums[i]) {
            if (print_debug_messages) {
        	cerr << i << ", ";
            }
            missing_seq.push_back(make_word_for_buffer(i));
        }
    }
    if (print_debug_messages && missing_seq.capacity()) {
	cerr << "}" << endl;
    }

    //Set correct number of lost sequences
    uint32_t miss_dim = missing_seq.size();

    //No missing sequences
    if (miss_dim == 0) {
        return true;
    }
    miss_cnt += miss_dim;

    uint32_t n_packets = 1;
    if (miss_dim > WORDS_PER_PACKET - 2) {
	n_packets += ceildiv(miss_dim - FirstMissingSeqsMessage::PAYLOAD_SIZE,
		MoreMissingSeqsMessage::PAYLOAD_SIZE);
    }

    // Transmit missing sequences as a new SDP Packet
    uint32_t seq_num_offset = 0;

    for (uint32_t i = 0; i < n_packets ; i++) {
	int words_in_this_packet;

	// If first, add n packets to list; otherwise just add data
	if (i == 0) {
	    // Get left over space / data size
	    words_in_this_packet = min(FirstMissingSeqsMessage::PAYLOAD_SIZE,
		    miss_dim - seq_num_offset);
	    // Make and send message
	    const FirstMissingSeqsMessage message(placement_x, placement_y,
		    placement_p, port_connection,
		    missing_seq.data() + seq_num_offset, words_in_this_packet,
		    n_packets);
	    sender.send_message(message);
	} else {
	    // Get left over space / data size
	    words_in_this_packet = min(MoreMissingSeqsMessage::PAYLOAD_SIZE,
		    miss_dim - seq_num_offset);
	    // Make and send message
	    const MoreMissingSeqsMessage message(placement_x, placement_y,
		    placement_p, port_connection,
		    missing_seq.data() + seq_num_offset,
		    words_in_this_packet);
	    sender.send_message(message);
	}

	seq_num_offset += words_in_this_packet;
	this_thread::sleep_for(DELAY_PER_SENDING);
    }

    return false;
}

//Function for computing expected maximum number of packets
uint32_t host_data_receiver::calculate_max_seq_num() const
{
    return ceildiv(length_in_bytes, NORMAL_PAYLOAD_LENGTH);
}

//Function for checking that all packets have been received
bool host_data_receiver::check() const
{
    if (received_count > max_seq_num + 1) {
        throw "Received more data than expected";
    }

    return received_count == max_seq_num + 1;
}

uint32_t host_data_receiver::calculate_offset(uint32_t seq_num) const
{
    return seq_num * NORMAL_PAYLOAD_LENGTH;
}

// Function for processing each received packet and checking end of transmission
bool host_data_receiver::process_data(
	const UDPConnection<BlockAlloc> &sender,
	bool is_end_of_stream,
	uint32_t seq_num,
	uint32_t content_length,
	const uint8_t *content_bytes)
{
    uint32_t offset = calculate_offset(seq_num);

    // Sanity checks
    if (seq_num > max_seq_num) {
        throw "Got insane sequence number";
    }
    if (offset + content_length > length_in_bytes) {
        throw "Receiving more data than expected";
    }
    if (is_end_of_stream || content_length == NORMAL_PAYLOAD_LENGTH) {
	// Store the data and the fact that we've processed this packet
	if (!received_seq_nums[seq_num]) {
	    memcpy(buffer.data() + offset, content_bytes, content_length);
	    received_count++;
	    received_seq_nums[seq_num] = true;
	}
    }

    // Determine if we're actually finished.
    if (!is_end_of_stream) {
	// Definitely not the end!
	return false;
    }
    if (check()) {
	return true;
    }
    // Finished but not complete; "Please sir, I want some more!"
    return retransmit_missing_sequences(sender);
}

void host_data_receiver::reader_thread(const UDPConnection<BlockAlloc> &receiver)
{
    // While socket is open add messages to the queue
    try {
	bool received;
	do {
	    buffer_t packet(RECEIVE_BUFFER_LENGTH);

	    if ((received = receiver.receive_data(packet))) {
		messqueue.push(packet);
	    }

	    // If the other thread threw an exception (no need for mutex, in
	    // the worst case this thread will add an additional value to the
	    // queue)
	    if (pcr.thrown) {
		return;
	    }
	} while (received && !finished);
    } catch (char const *e) {
	rdr.val = e;
	rdr.thrown = true;
    }
}

void host_data_receiver::processor_thread(const UDPConnection<BlockAlloc> &sender)
{
    uint32_t timeoutcount = 0;
    bool finished = false;

    while (!finished && !rdr.thrown) {
        try {
            buffer_t p = messqueue.pop();
	    if (!p.empty()) {
		process_data(sender, finished, p);
	    }
        } catch (TimeoutQueueException &e) {
            if (timeoutcount > TIMEOUT_RETRY_LIMIT) {
                pcr.val = "Failed to hear from the machine. "
                        "Please try removing firewalls";
                pcr.thrown = true;
                return;
            }

            timeoutcount++;

            if (!finished) {
                // retransmit missing packets
                finished = retransmit_missing_sequences(sender);
            }
        } catch (const char *e) {
            pcr.val = e;
            pcr.thrown = true;
            return;
        }
    }
}

// Function externally callable for data gathering. It returns a buffer
// containing read data
const uint8_t *host_data_receiver::get_data()
{
    try {
	if (!started) {
	    // create connection
	    UDPConnection<BlockAlloc> connection(SDP_PORT, hostname);
	    started = true;

	    // send the initial command to start data transmission
	    send_initial_command(connection, connection);

	    thread reader(&host_data_receiver::reader_thread, this,
		    ref(connection));
	    thread processor(&host_data_receiver::processor_thread, this,
		    ref(connection));

	    reader.join();
	    processor.join();
	    // The socket is closed automatically at this point
	}

        if (pcr.thrown) {
            cerr << "ERROR: " << pcr.val << endl;
            return nullptr;
        } else if (rdr.thrown && !finished) {
            cerr << "ERROR: " << rdr.val << endl;
            return nullptr;
        }
	return buffer.data();
    } catch (char const *e) {
        cerr << e << endl;
        return nullptr;
    }
}

// Function externally callable for data gathering. It can be called by
// multiple threads simultaneously
void host_data_receiver::get_data_threadable(
	std::string &filepath_read,
	std::string &filepath_missing)
{
    auto data_buffer = get_data();

    if (data_buffer && !filepath_read.empty()) {
	std::fstream output(filepath_read, ios::out | ios::binary);
	output.write(reinterpret_cast<const char *>(data_buffer), length_in_bytes);
    }
    if (!filepath_missing.empty()) {
	std::fstream missing(filepath_missing, ios::out);
	missing << miss_cnt << endl;
    }
}

uint8_t *BlockAlloc::allocate_chunk(std::size_t n) {
    uint32_t counter = (first++) % NUM_BLOCKS;
    return blocks[counter];
}

void BlockAlloc::deallocate(uint8_t *p, std::size_t n) {
    uint32_t counter = (last++) % NUM_BLOCKS;
}

uint32_t BlockAlloc::first;
uint32_t BlockAlloc::last;
uint8_t BlockAlloc::blocks[1024 * 1024][300];


#ifdef PYBIND11_MODULE
namespace py = pybind11;

// Same behaviour of get_data() function, but returns a valid type for python
// code
py::object host_data_receiver::get_data_for_python() {
    auto data_buffer = get_data();
    if (data_buffer == nullptr) {
	return py::none();
    }
    std::string str(
	    reinterpret_cast<const char *>(data_buffer), length_in_bytes);
    return py::bytes(str);
}

//Python Binding
PYBIND11_MODULE(host_data_receiver, m) {
    m.doc() = "C++ data speed up packet gatherer machine vertex";
    py::class_<host_data_receiver>(m, "host_data_receiver")
	.def(py::init<int, int, int, int, const char *, int, int, int, int, int>())
	.def("get_data_threadable", &host_data_receiver::get_data_threadable)
	.def("get_data", &host_data_receiver::get_data_for_python);
}
#endif
