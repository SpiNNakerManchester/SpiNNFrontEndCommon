#include "host_data_receiver.h"
#include <vector>

using namespace std;
//namespace py = pybind11;

//Constants
static const uint32_t SDP_PACKET_START_SENDING_COMMAND_ID = 100;
static const uint32_t SDP_PACKET_START_MISSING_SEQ_COMMAND_ID = 1000;
static const uint32_t SDP_PACKET_MISSING_SEQ_COMMAND_ID = 1001;
//static const int SDP_PACKET_PORT = 2;
static const uint32_t SDP_RETRANSMISSION_HEADER_SIZE = 10;
static const uint32_t SDP_PACKET_START_SENDING_COMMAND_MESSAGE_SIZE = 3;

// time out constants
static const int TIMEOUT_PER_RECEIVE_IN_SECONDS = 1;
static const int TIMEOUT_PER_SENDING_IN_MICROSECONDS = 10000;

// consts for data and converting between words and bytes
//static const int SDRAM_READING_SIZE_IN_BYTES_CONVERTER = 1024 * 1024;
static const int DATA_PER_FULL_PACKET = 68;
static const int DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM = DATA_PER_FULL_PACKET
        - 1;
static const int WORD_TO_BYTE_CONVERTER = 4;
static const int LENGTH_OF_DATA_SIZE = 4;
static const int END_FLAG_SIZE = 4;
static const int END_FLAG_SIZE_IN_BYTES = 4;
static const int SEQUENCE_NUMBER_SIZE = 4;
static const int END_FLAG = 0xFFFFFFFF;
static const int LAST_MESSAGE_FLAG_BIT_MASK = 0x80000000;
static const int TIMEOUT_RETRY_LIMIT = 20;

int miss_cnt;

// Constructor
host_data_receiver::host_data_receiver(
        int port_connection,
        int placement_x,
        int placement_y,
        int placement_p,
        char *hostname,
        int length_in_bytes,
        int memory_address,
        int chip_x,
        int chip_y,
        int iptag)
{
    this->port_connection = port_connection;
    this->placement_x = placement_x;
    this->placement_y = placement_y;
    this->placement_p = placement_p;
    this->hostname = hostname;
    this->length_in_bytes = (uint32_t) length_in_bytes;
    this->memory_address = (uint32_t) memory_address;
    this->chip_x = chip_x;
    this->chip_y = chip_y;
    this->iptag = iptag;

    // allocate queue for messages
    messqueue = new PQueue<packet>();

    buffer = new char[length_in_bytes];

    this->max_seq_num = calculate_max_seq_num(length_in_bytes);
    this->rdr.thrown = false;
    this->pcr.thrown = false;
    this->finished = false;

    miss_cnt = 0;
}

void host_data_receiver::receive_message(
	UDPConnection &receiver, vector<uint8_t> working_buffer)
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
    uint32_t data[DATA_PER_FULL_PACKET];
    uint32_t i;

    //Calculate number of missing sequences based on difference between
    //expected and received
    uint32_t miss_dim = max_seq_num - received_seq_nums.size();
    uint32_t *missing_seq = new uint32_t[miss_dim];
    uint32_t j = 0;

    // Calculate missing sequence numbers and add them to "missing"
    for (i = 0; i < max_seq_num ; i++) {
        if (received_seq_nums.find(i) == received_seq_nums.end()) {
            missing_seq[j++] = i;
        }
    }

    //Set correct number of lost sequences
    miss_dim = j;

    //No missing sequences
    if (miss_dim == 0) {
        return true;
    }

    uint32_t n_packets = 1;
    int length_via_format2 = miss_dim - (DATA_PER_FULL_PACKET - 2);

    if (length_via_format2 > 0) {
        n_packets += ceildiv(length_via_format2, DATA_PER_FULL_PACKET - 1);
    }

    // Transmit missing sequences as a new SDP Packet
    bool first = true;
    int seq_num_offset = 0;

    for (i = 0; i < n_packets ; i++) {
	uint32_t datasize;
        int length_left_in_packet = DATA_PER_FULL_PACKET;
        int offset = 0;
        int size_of_data_left_to_transmit;

        // If first, add n packets to list; otherwise just add data
        if (first) {
            // Get left over space / data size
            size_of_data_left_to_transmit = min(length_left_in_packet - 2,
                    (int) miss_dim - seq_num_offset);

            datasize = size_of_data_left_to_transmit + 2;

            // Pack flag and n packets
            data[0] = SDP_PACKET_START_MISSING_SEQ_COMMAND_ID;
            data[1] = n_packets;

            // Update state
            offset += 2;
            length_left_in_packet -= 2;
            first = false;
        } else {
            // Get left over space / data size
            size_of_data_left_to_transmit = min(
                    DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM,
                    (int) miss_dim - seq_num_offset);

            datasize = size_of_data_left_to_transmit + 1;

            // Pack flag
            data[offset] = SDP_PACKET_MISSING_SEQ_COMMAND_ID;

            offset += 1;
            length_left_in_packet -= 1;
        }

        memcpy(((char *) data) + offset * sizeof(uint32_t),
                missing_seq + seq_num_offset,
                size_of_data_left_to_transmit * sizeof(uint32_t));

        seq_num_offset += length_left_in_packet;

        SDPMessage message(placement_x, placement_y,
                placement_p, port_connection,
                SDPMessage::REPLY_NOT_EXPECTED, 255, 255, 255, 0, 0,
                (char *) data, datasize * sizeof(uint32_t));
        sender.send_message(message);

        usleep(TIMEOUT_PER_SENDING_IN_MICROSECONDS);
    }

    delete[] missing_seq;
    return false;
}

//Function for computing expected maximum number of packets
uint32_t host_data_receiver::calculate_max_seq_num(uint32_t length)
{
    return ceildiv(length,
            DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM * WORD_TO_BYTE_CONVERTER);
}

//Function for checking that all packets have been received
bool host_data_receiver::check(
        set<uint32_t> &received_seq_nums,
        uint32_t max_needed)
{
    uint32_t recvsize = received_seq_nums.size();

    if (recvsize > max_needed + 1) {
        throw "ERROR: Received more data than expected";
    }

    return recvsize == max_needed + 1;
}

// Function for processing each received packet and checking end of transmission
void host_data_receiver::process_data(
        UDPConnection &sender,
        bool &finished,
        set<uint32_t> &received_seq_nums,
        char *recvdata,
        int datalen)
{
    //Data size of the packet
    int length_of_data = datalen;

    uint32_t first_packet_element;
    memcpy(&first_packet_element, recvdata, sizeof(uint32_t));

    // Unpack the first word
    uint32_t seq_num = first_packet_element & 0x7FFFFFFF;
    bool is_end_of_stream =
            (first_packet_element & LAST_MESSAGE_FLAG_BIT_MASK) != 0;

    if (seq_num > max_seq_num) {
        throw "ERROR: Got insane sequence number";
    }

    uint32_t offset = seq_num * DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM
            * WORD_TO_BYTE_CONVERTER;

    uint32_t true_data_length = offset + length_of_data - SEQUENCE_NUMBER_SIZE;

    if (true_data_length > length_in_bytes) {
        throw "ERROR: Receiving more data than expected";
    }

    if (is_end_of_stream && (length_of_data == END_FLAG_SIZE_IN_BYTES)) {
        // empty
    } else {
        memcpy(buffer + offset, recvdata + SEQUENCE_NUMBER_SIZE,
                true_data_length - offset);
    }

    received_seq_nums.insert(seq_num);

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
	int recvd;
	packet p;

	do {
            recvd = receiver->receive_data(p.content, 400);
            p.size = recvd;
	    if (recvd) {
		messqueue->push(p);
	    }

	    // If the other thread threw an exception (no need for mutex, in
	    // the worst case this thread will add an additional value to the
	    // queue)
	    if (pcr.thrown) {
		return;
	    }
	} while (recvd);
    } catch (char const *e) {
	rdr.val = e;
	rdr.thrown = true;
	return;
    }
}

void host_data_receiver::processor_thread(UDPConnection *sender)
{
    int timeoutcount = 0, datalen;
    bool finished = false;
    set<uint32_t> received_seq_nums;
    packet p;

    while (!finished) {
        try {
            p = messqueue->pop();
            datalen = p.size;

            process_data(*sender, finished, received_seq_nums, p.content,
                    datalen);
        } catch (TimeoutQueueException e) {
            if (timeoutcount > TIMEOUT_RETRY_LIMIT) {
                pcr.val = "ERROR: Failed to hear from the machine. "
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

        if (rdr.thrown) {
            return;
        }
    }

    // close socket and inform the reader that transmission is completed
    delete sender;
    finished = true;
}

// Function externally callable for data gathering. It returns a buffer
// containing read data
char *host_data_receiver::get_data()
{
    try {
        // create connection
	{
	    UDPConnection sender(0, NULL, 17893, hostname);

	    // send the initial command to start data transmission
	    send_initial_command(sender, sender);

	    thread reader(
		    &host_data_receiver::reader_thread, this, &sender);
	    thread processor(
		    &host_data_receiver::processor_thread, this, &sender);

	    reader.join();
	    processor.join();
	}

        if (pcr.thrown) {
            cout << pcr.val << endl;
            return NULL;
        } else if (rdr.thrown && !finished) {
            cout << rdr.val << endl;
            return NULL;
        }
    } catch (char const *e) {
        cout << e << endl;
        return NULL;
    }

    return buffer;
}

/*
 //Same behavior of get_data() function, but returns a valid type for python
 code
 py::bytes host_data_receiver::get_data_for_python(
 char *hostname, int port_connection, int placement_x, int placement_y,
 int placement_p, int length_in_bytes, int memory_address, int chip_x,
 int chip_y, int iptag) {

 get_data();

 std::string *str = new string((const char *)this->buffer, length_in_bytes);

 return py::bytes(*str);
 }*/

// Function externally callable for data gathering. It can be called by
// multiple threads simultaneously
void host_data_receiver::get_data_threadable(
        char *filepath_read,
        char *filepath_missing)
{
    FILE *fp1, *fp2;

    get_data();

    fp1 = fopen(filepath_read, "wb");
    fp2 = fopen(filepath_missing, "w");

    fwrite(this->buffer, sizeof(char), length_in_bytes, fp1);

    fprintf(fp2, "%d\n", miss_cnt);

    fclose(fp1);
    fclose(fp2);
}
/*
 //Python Binding

 PYBIND11_MODULE(host_data_receiver, m) {

 m.doc() = "C++ data speed up packet gatherer machine vertex";

 py::class_<host_data_receiver>(m, "host_data_receiver")
 .def(py::init<>())
 .def("get_data_threadable", &host_data_receiver::get_data_threadable)
 .def("get_data", &host_data_receiver::get_data)
 .def("get_data_for_python", &host_data_receiver::get_data_for_python);
 }
 */
