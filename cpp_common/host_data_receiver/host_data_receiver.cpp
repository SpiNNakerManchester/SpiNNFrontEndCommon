#include <cstdint>
#include "host_data_receiver.h"
#include <vector>
#include <cassert>
#include <chrono>
#include <fstream>
#include "math.h"

using namespace std;
using namespace std::literals::chrono_literals; // BLACK MAGIC!

static const int SDP_PORT = 17893;
static const int MAX_SDP_PACKET_LENGTH = 280;

//Constants
static constexpr uint32_t SDP_PACKET_START_SENDING_COMMAND_ID = 100;
static constexpr uint32_t SDP_PACKET_START_MISSING_SEQ_COMMAND_ID = 1000;
static constexpr uint32_t SDP_PACKET_MISSING_SEQ_COMMAND_ID = 1001;

// time out constants
static constexpr auto DELAY_PER_SENDING = 10000us;

// consts for data and converting between words and bytes
//static const int SDRAM_READING_SIZE_IN_BYTES_CONVERTER = 1024 * 1024;
static constexpr uint32_t WORDS_PER_PACKET = 68;
static constexpr uint32_t WORDS_PER_PACKET_WITH_SEQUENCE_NUM = WORDS_PER_PACKET - 1;
static constexpr uint32_t WORD_TO_BYTE_CONVERTER = 4;
static constexpr int RECEIVE_BUFFER_LENGTH = WORDS_PER_PACKET * WORD_TO_BYTE_CONVERTER;
static constexpr int TIMEOUT_RETRY_LIMIT = 20;

class OneWayMessage: public SDPMessage {
public:
    OneWayMessage(int x, int y, int p, int port, void *data, int length) :
	    SDPMessage(x, y, p, port, SDPMessage::REPLY_NOT_EXPECTED, 255,
		    255, 255, 0, 0, data, length)
    {
    }
};

class TwoWayMessage: public SDPMessage {
public:
    TwoWayMessage(int x, int y, int p, int port, void *data, int length) :
	    SDPMessage(x, y, p, port, SDPMessage::REPLY_EXPECTED, 255,
		    255, 255, 0, 0, data, length)
    {
    }
};

class SetIPTagMessage: public TwoWayMessage {
public:
    SetIPTagMessage(
	    int chip_x,
	    int chip_y,
	    int iptag,
	    uint32_t target_ip,
	    uint32_t target_port) :
	    TwoWayMessage(chip_x, chip_y, 0, 0, &payload, sizeof(payload))
    {
	payload.cmd = host_data_receiver::SET_IP_TAG;
	payload.seq = 0;
	int strip_sdp = 1;
	payload.packed = (strip_sdp << 28) | (1 << 16) | iptag;
	payload.port = target_port;
	payload.ip = target_ip;
    }
private:
    struct SCP_SetIPTag_Payload {
	uint16_t cmd;
	uint16_t seq;
	uint32_t packed;
	uint32_t port;
	uint32_t ip;
    } payload;
};

class StartSendingMessage: public OneWayMessage {
public:
    StartSendingMessage(
	    int x,
	    int y,
	    int p,
	    int port,
	    uint32_t address,
	    uint32_t length) :
	    OneWayMessage(x, y, p, port, (char *) &payload, sizeof(payload))
    {
	payload.cmd = make_word_for_buffer(SDP_PACKET_START_SENDING_COMMAND_ID);
	payload.address = make_word_for_buffer(address);
	payload.length = make_word_for_buffer(length);
    }
private:
    struct Payload {
	uint32_t cmd;
	uint32_t address;
	uint32_t length;
    } payload;
};

class FirstMissingSeqsMessage: public OneWayMessage {
public:
    static constexpr uint32_t const& PAYLOAD_SIZE = WORDS_PER_PACKET - 2;
    FirstMissingSeqsMessage(
	    int x,
	    int y,
	    int p,
	    int port,
	    const uint32_t *data,
	    uint32_t length,
	    uint32_t num_packets) :
	    OneWayMessage(x, y, p, port, buffer,
		    (length + 2) * sizeof(uint32_t))
    {
	buffer[0] = make_word_for_buffer(
		SDP_PACKET_START_MISSING_SEQ_COMMAND_ID);
	buffer[1] = make_word_for_buffer(num_packets);
	memcpy(&buffer[2], data, length * sizeof(uint32_t));
    }
private:
    uint32_t buffer[WORDS_PER_PACKET];
};

class MoreMissingSeqsMessage: public OneWayMessage {
public:
    static constexpr uint32_t const& PAYLOAD_SIZE = WORDS_PER_PACKET - 1;
    MoreMissingSeqsMessage(
	    int x,
	    int y,
	    int p,
	    int port,
	    const uint32_t *data,
	    uint32_t length) :
	    OneWayMessage(x, y, p, port, buffer,
		    (length + 1) * sizeof(uint32_t))
    {
	buffer[0] = make_word_for_buffer(SDP_PACKET_MISSING_SEQ_COMMAND_ID);
	memcpy(&buffer[1], data, length * sizeof(uint32_t));
    }
private:
    uint32_t buffer[WORDS_PER_PACKET];
};

void host_data_receiver::receive_message(
	UDPConnection &receiver, vector<uint8_t> &working_buffer)
{
    working_buffer.resize(MAX_SDP_PACKET_LENGTH);
    receiver.receive_data(working_buffer);
}

//Function for asking data to the SpiNNaker system
void host_data_receiver::send_initial_command(
        UDPConnection &sender,
        UDPConnection &receiver)
{
    //Build an SCP request to set up the IP Tag associated to this socket
    SetIPTagMessage set_iptag_req(chip_x, chip_y, iptag,
	    receiver.get_local_ip(), receiver.get_local_port());

    //Send SCP request and receive (and ignore) response
    sender.send_message(set_iptag_req);

    std::vector<uint8_t> working_buffer;
    receive_message(sender, working_buffer);

    // Create Data request SDP packet
    StartSendingMessage message(placement_x, placement_y, placement_p,
	    port_connection, memory_address, length_in_bytes);
    //send message
    sender.send_message(message);
}

static inline uint32_t ceildiv(uint32_t numerator, uint32_t denominator)
{
    return (uint32_t) ceil(numerator / (float) denominator);
}

// Function for asking for retransmission of missing sequences
bool host_data_receiver::retransmit_missing_sequences(
        UDPConnection &sender,
        set<uint32_t> &received_seq_nums)
{
    //Calculate number of missing sequences based on difference between
    //expected and received
    vector<uint32_t> missing_seq(0);
    // We know how many elements we expect to be missing
    missing_seq.reserve(max_seq_num - received_seq_nums.size());

    // Calculate missing sequence numbers and add them to "missing"
    for (uint32_t i = 0; i < max_seq_num ; i++) {
        if (received_seq_nums.find(i) == received_seq_nums.end()) {
            missing_seq.push_back(make_word_for_buffer(i));
        }
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
	n_packets += ceildiv(miss_dim - (WORDS_PER_PACKET - 2),
		WORDS_PER_PACKET_WITH_SEQUENCE_NUM);
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
	    FirstMissingSeqsMessage message(placement_x, placement_y,
		    placement_p, port_connection,
		    missing_seq.data() + seq_num_offset, words_in_this_packet,
		    n_packets);
	    sender.send_message(message);
	} else {
	    // Get left over space / data size
	    words_in_this_packet = min(MoreMissingSeqsMessage::PAYLOAD_SIZE,
		    miss_dim - seq_num_offset);
	    // Make and send message
	    MoreMissingSeqsMessage message(placement_x, placement_y,
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

static constexpr uint32_t NORMAL_PAYLOAD_LENGTH =
	WORDS_PER_PACKET_WITH_SEQUENCE_NUM * WORD_TO_BYTE_CONVERTER;

//Function for computing expected maximum number of packets
uint32_t host_data_receiver::calculate_max_seq_num()
{
    return ceildiv(length_in_bytes, NORMAL_PAYLOAD_LENGTH);
}

//Function for checking that all packets have been received
bool host_data_receiver::check(
        set<uint32_t> &received_seq_nums,
        uint32_t max_needed)
{
    uint32_t recvsize = received_seq_nums.size();

    if (recvsize > max_needed + 1) {
        throw "Received more data than expected";
    }

    return recvsize == max_needed + 1;
}

uint32_t host_data_receiver::calculate_offset(uint32_t seq_num)
{
    return seq_num * NORMAL_PAYLOAD_LENGTH;
}

// Function for processing each received packet and checking end of transmission
bool host_data_receiver::process_data(
	UDPConnection &sender,
	set<uint32_t> &received_seq_nums,
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
	memcpy(buffer.data() + offset, content_bytes, content_length);
	if (!received_seq_nums.insert(seq_num).second) {
	    // already received this packet!
	    cerr << "WARNING: received " << seq_num << " at least twice"
		    << endl;
	}
    }

    // Determine if we're actually finished.
    if (!is_end_of_stream) {
	// Definitely not the end!
	return false;
    }
    if (check(received_seq_nums, max_seq_num)) {
	return true;
    }
    // Finished but not complete; "Please sir, I want some more!"
    return retransmit_missing_sequences(sender, received_seq_nums);
}

void host_data_receiver::reader_thread(UDPConnection *receiver)
{
    // While socket is open add messages to the queue
    try {
	std::vector<uint8_t> packet;

	do {
	    packet.resize(RECEIVE_BUFFER_LENGTH);
	    memset(packet.data(), 0xFF, packet.size());
	    if (receiver->receive_data(packet)) {
		messqueue.push(packet);
	    }

	    // If the other thread threw an exception (no need for mutex, in
	    // the worst case this thread will add an additional value to the
	    // queue)
	    if (pcr.thrown) {
		return;
	    }
	} while (!packet.empty() && !finished);
    } catch (char const *e) {
	rdr.val = e;
	rdr.thrown = true;
    }
}

void host_data_receiver::processor_thread(UDPConnection *sender)
{
    int timeoutcount = 0;
    bool finished = false;
    set<uint32_t> received_seq_nums;

    while (!finished && !rdr.thrown) {
        try {
	    std::vector<uint8_t> p = messqueue.pop();
	    if (!p.empty())
		process_data(*sender, finished, received_seq_nums, p);
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
                finished = retransmit_missing_sequences(*sender,
                        received_seq_nums);
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
	    UDPConnection connection(SDP_PORT, hostname);
	    started = true;

	    // send the initial command to start data transmission
	    send_initial_command(connection, connection);

	    thread reader(
		    &host_data_receiver::reader_thread, this, &connection);
	    thread processor(
		    &host_data_receiver::processor_thread, this, &connection);

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
        const char *filepath_read,
        const char *filepath_missing)
{

    auto data_buffer = get_data();

    if (filepath_read) {
	std::fstream output(filepath_read, ios::out | ios::binary);
	output.write((char *) data_buffer, length_in_bytes);
    }
    if (filepath_missing) {
	std::fstream missing(filepath_missing, ios::out);
	missing << miss_cnt << endl;
    }
}

#if 0
namespace py = pybind11;

// Same behaviour of get_data() function, but returns a valid type for python
// code
py::bytes host_data_receiver::get_data_for_python(
	char *hostname, int port_connection, int placement_x, int placement_y,
	int placement_p, int length_in_bytes, int memory_address, int chip_x,
	int chip_y, int iptag) {
    auto data_buffer = get_data();

    std::string *str = new string(
	    (const char *) data_buffer, length_in_bytes);

    return py::bytes(*str);
}

//Python Binding
PYBIND11_MODULE(host_data_receiver, m) {
    m.doc() = "C++ data speed up packet gatherer machine vertex";
    py::class_<host_data_receiver>(m, "host_data_receiver")
	 .def(py::init<>())
	 .def("get_data_threadable", &host_data_receiver::get_data_threadable)
	 .def("get_data", &host_data_receiver::get_data)
	 .def("get_data_for_python", &host_data_receiver::get_data_for_python);
}
#endif
