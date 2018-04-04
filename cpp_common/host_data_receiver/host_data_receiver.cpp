#include "host_data_receiver.h"
#include <vector>
#include <cassert>
#include <chrono>

using namespace std;
using namespace std::literals::chrono_literals; // BLACK MAGIC!

static const int SDP_PORT = 17893;

//Constants
static const uint32_t SDP_PACKET_START_SENDING_COMMAND_ID = 100;
static const uint32_t SDP_PACKET_START_MISSING_SEQ_COMMAND_ID = 1000;
static const uint32_t SDP_PACKET_MISSING_SEQ_COMMAND_ID = 1001;
//static const int SDP_PACKET_PORT = 2;
static const uint32_t SDP_RETRANSMISSION_HEADER_SIZE = 10;
static const uint32_t SDP_PACKET_START_SENDING_COMMAND_MESSAGE_SIZE = 3;

// time out constants
static const auto DELAY_PER_SENDING = 10000us;

// consts for data and converting between words and bytes
//static const int SDRAM_READING_SIZE_IN_BYTES_CONVERTER = 1024 * 1024;
static const uint32_t WORDS_PER_PACKET = 68;
static const uint32_t WORDS_PER_PACKET_WITH_SEQUENCE_NUM = WORDS_PER_PACKET - 1;
static const uint32_t WORD_TO_BYTE_CONVERTER = 4;
static const uint32_t LENGTH_OF_DATA_SIZE = 4;
static const uint32_t END_FLAG_SIZE = 4;
static const uint32_t END_FLAG_SIZE_IN_BYTES = 4;
static const uint32_t SEQUENCE_NUMBER_SIZE = 4;
static const uint32_t END_FLAG = 0xFFFFFFFF;
static const uint32_t LAST_MESSAGE_FLAG_BIT_MASK = 0x80000000;
static const uint32_t SEQ_NUM_MASK = ~LAST_MESSAGE_FLAG_BIT_MASK;
static const int TIMEOUT_RETRY_LIMIT = 20;

static inline uint32_t get_word_from_buffer(
	vector<uint8_t> &buffer, uint32_t offset)
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

void host_data_receiver::receive_message(
	UDPConnection &receiver, vector<uint8_t> &working_buffer)
{
    working_buffer.resize(300);
    receiver.receive_data(working_buffer);
}

//Function for asking data to the SpiNNaker system
void host_data_receiver::send_initial_command(
        UDPConnection &sender,
        UDPConnection &receiver)
{
    //Build an SCP request to set up the IP Tag associated to this socket
    int strip_sdp = 1;
    struct SetIPTagMessage {
	uint16_t cmd;
	uint16_t seq;
	uint32_t packed;
	uint32_t port;
	uint32_t ip;
    };
    assert(sizeof(SetIPTagMessage) == 16);
    SetIPTagMessage scp_req;
    scp_req.cmd = SET_IP_TAG;
    scp_req.seq = 0;
    scp_req.packed = (strip_sdp << 28) | (1 << 16) | iptag;
    scp_req.port = receiver.get_local_port();
    scp_req.ip = receiver.get_local_ip();

    //fprintf(stderr, "port%d\n", receiver->get_local_port());

    SDPMessage ip_tag_message(chip_x, chip_y, 0, 0,
            SDPMessage::REPLY_EXPECTED, 255, 255, 255, 0, 0,
	    (char *) &scp_req, sizeof(scp_req));
    //Send SCP request and receive (and ignore) response
    sender.send_message(ip_tag_message);

    std::vector<uint8_t> working_buffer;
    receive_message(sender, working_buffer);

    // Create Data request SDP packet
    struct DataRequestMessage {
	uint32_t cmd;
	uint32_t address;
	uint32_t length;
    };
    DataRequestMessage start_message_data;

    // add data
    start_message_data.cmd = SDP_PACKET_START_SENDING_COMMAND_ID;
    start_message_data.address = memory_address;
    start_message_data.length = length_in_bytes;

    // build SDP message
    SDPMessage message(placement_x, placement_y,
            placement_p, port_connection,
            SDPMessage::REPLY_NOT_EXPECTED, 255, 255, 255, 0, 0,
            (char *) &start_message_data, sizeof(start_message_data));
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
    uint32_t data[WORDS_PER_PACKET];
    uint32_t i;

    //Calculate number of missing sequences based on difference between
    //expected and received
    vector<uint32_t> missing_seq(0);
    // We know how many elements we expect to be missing
    missing_seq.reserve(max_seq_num - received_seq_nums.size());

    // Calculate missing sequence numbers and add them to "missing"
    for (i = 0; i < max_seq_num ; i++) {
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
    int seq_num_offset = 0;

    for (i = 0; i < n_packets ; i++) {
	uint32_t datasize;
        int length_left_in_packet = WORDS_PER_PACKET;
        int offset;
        int miss_seq_words_to_transmit;

        // If first, add n packets to list; otherwise just add data
        if (i == 0) {
            // Get left over space / data size
            miss_seq_words_to_transmit = min(WORDS_PER_PACKET - 2,
                    miss_dim - seq_num_offset);
            datasize = miss_seq_words_to_transmit + 2;

            // Pack flag and n packets
            data[0] = make_word_for_buffer(SDP_PACKET_START_MISSING_SEQ_COMMAND_ID);
            data[1] = make_word_for_buffer(n_packets);

            // Update state
            offset = 2;
            length_left_in_packet -= 2;
        } else {
            // Get left over space / data size
            miss_seq_words_to_transmit = min(
                    WORDS_PER_PACKET_WITH_SEQUENCE_NUM,
		    miss_dim - seq_num_offset);
            datasize = miss_seq_words_to_transmit + 1;

            // Pack flag
            data[0] = make_word_for_buffer(SDP_PACKET_MISSING_SEQ_COMMAND_ID);

            offset = 1;
            length_left_in_packet--;
        }

        memcpy(&data[offset], missing_seq.data() + seq_num_offset,
                miss_seq_words_to_transmit * sizeof(uint32_t));

        seq_num_offset += length_left_in_packet;

        SDPMessage message(placement_x, placement_y,
                placement_p, port_connection,
                SDPMessage::REPLY_NOT_EXPECTED, 255, 255, 255, 0, 0,
                (char *) data, datasize * sizeof(uint32_t));
        sender.send_message(message);

        this_thread::sleep_for(DELAY_PER_SENDING);
    }

    return false;
}

//Function for computing expected maximum number of packets
uint32_t host_data_receiver::calculate_max_seq_num()
{
    return ceildiv(length_in_bytes,
            WORDS_PER_PACKET_WITH_SEQUENCE_NUM * WORD_TO_BYTE_CONVERTER);
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
    return seq_num * WORDS_PER_PACKET_WITH_SEQUENCE_NUM
	    * WORD_TO_BYTE_CONVERTER;
}

// Function for processing each received packet and checking end of transmission
void host_data_receiver::process_data(
        UDPConnection &sender,
        bool &finished,
        set<uint32_t> &received_seq_nums,
        vector<uint8_t> &recvdata)
{
    uint32_t first_packet_element = get_word_from_buffer(recvdata, 0);
    uint32_t content_length = recvdata.size() - SEQUENCE_NUMBER_SIZE;
    const uint8_t *content_bytes = recvdata.data() + SEQUENCE_NUMBER_SIZE;

    // Unpack the first word
    uint32_t seq_num = first_packet_element & SEQ_NUM_MASK;
    bool is_end_of_stream =
            (first_packet_element & LAST_MESSAGE_FLAG_BIT_MASK) != 0;

    if (seq_num > max_seq_num) {
        throw "Got insane sequence number";
    }

    uint32_t offset = calculate_offset(seq_num);

    if (offset + content_length > length_in_bytes) {
        throw "Receiving more data than expected";
    }

    if (content_length != 0) {
	memcpy(buffer.data() + offset, content_bytes, content_length);
    }

    if (!received_seq_nums.insert(seq_num).second) {
	// already received this packet!
	cerr << "WARNING: received " << seq_num << " at least twice" << endl;
    }

    if (is_end_of_stream) {
        if (!check(received_seq_nums, max_seq_num)) {
            finished = retransmit_missing_sequences(
        	    sender, received_seq_nums);
        } else {
            finished = true;
        }
    }
}

void host_data_receiver::reader_thread(UDPConnection *receiver)
{
    // While socket is open add messages to the queue
    try {
	std::vector<uint8_t> packet;

	do {
	    packet.resize(400);
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
    FILE *fp1, *fp2 = nullptr;

    auto data_buffer = get_data();

    fp1 = fopen(filepath_read, "wb");
    fwrite(data_buffer, sizeof(uint8_t), length_in_bytes, fp1);
    fclose(fp1);

    if (filepath_missing) {
	fp2 = fopen(filepath_missing, "w");
	fprintf(fp2, "%d\n", miss_cnt);
	fclose(fp2);
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
