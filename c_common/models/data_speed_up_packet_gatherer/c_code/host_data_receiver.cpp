#include "host_data_receiver.h"

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
static const int DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM =
	DATA_PER_FULL_PACKET - 1;
static const int WORD_TO_BYTE_CONVERTER = 4;
static const int LENGTH_OF_DATA_SIZE = 4;
static const int END_FLAG_SIZE = 4;
static const int END_FLAG_SIZE_IN_BYTES = 4;
static const int SEQUENCE_NUMBER_SIZE = 4;
static const int END_FLAG = 0xFFFFFFFF;
static const int LAST_MESSAGE_FLAG_BIT_MASK = 0x80000000;
static const int TIMEOUT_RETRY_LIMIT = 20;

//vector<uint32_t> missing;

// Constructor
host_data_receiver::host_data_receiver(int port_connection, int placement_x, int placement_y, int placement_p,
		char *hostname, int length_in_bytes, int memory_address, int chip_x, int chip_y, int iptag) {

	this->port_connection = port_connection; 
	this->placement_x = placement_x; 
	this->placement_y = placement_y; 
	this->placement_p = placement_p;
	this-> hostname = hostname;
	this->length_in_bytes = (uint32_t)length_in_bytes; 
	this->memory_address = (uint32_t)memory_address;
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
}

// Function for allocating an SCP Message
char * host_data_receiver::build_scp_req(uint16_t cmd, uint32_t port, int strip_sdp, uint32_t ip_address) {

	uint16_t seq = 0;
	uint32_t arg = 0;

	char *buffertmp = new char[4*sizeof(uint32_t)];

	memcpy(buffertmp, &cmd, sizeof(uint16_t));
	memcpy(buffertmp+sizeof(uint16_t), &seq, sizeof(uint16_t));

	arg = arg | (strip_sdp << 28) | (1 << 16) | this->iptag;
	memcpy(buffertmp+sizeof(uint32_t), &arg, sizeof(uint32_t));
	memcpy(buffertmp+2*sizeof(uint32_t), &port, sizeof(uint32_t));
	memcpy(buffertmp+3*sizeof(uint32_t), &ip_address, sizeof(uint32_t));


	return buffertmp;
}


//Function for asking data to the SpiNNaker system
void host_data_receiver::send_initial_command(UDPConnection *sender, UDPConnection *receiver) {

	//Build an SCP request to set up the IP Tag associated to this socket
	char *scp_req = build_scp_req((uint16_t)26, receiver->get_local_port(), 1, receiver->get_local_ip());

	SDPMessage ip_tag_message = SDPMessage(
		this->chip_x, this->chip_y, 0, 0, SDPMessage::REPLY_EXPECTED,
		255, 255, 255, 0, 0, scp_req, 4*sizeof(uint32_t));

	//Send SCP request
	sender->send_data(ip_tag_message.convert_to_byte_array(),
					 ip_tag_message.length_in_bytes());

	char buf[300];

	sender->receive_data(buf, 300);

    // Create Data request SDP packet
	char start_message_data[3*sizeof(uint32_t)];

    // add data
	memcpy(start_message_data, &SDP_PACKET_START_SENDING_COMMAND_ID, sizeof(uint32_t));
	memcpy(start_message_data+sizeof(uint32_t), &this->memory_address, sizeof(uint32_t));
	memcpy(start_message_data+2*sizeof(uint32_t), &this->length_in_bytes, sizeof(uint32_t));

    // build SDP message
    SDPMessage message = SDPMessage(
        this->placement_x, this->placement_y, this->placement_p, this->port_connection,
        SDPMessage::REPLY_NOT_EXPECTED, 255, 255, 255, 0, 0, start_message_data,
        3*sizeof(uint32_t));

    //send message
    sender->send_data(message.convert_to_byte_array(),
                     message.length_in_bytes());
}


// Function for asking for retransmission of missing sequences
bool host_data_receiver::retransmit_missing_sequences(UDPConnection *sender, set<uint32_t> *received_seq_nums) {

		int length_via_format2, seq_num_offset, length_left_in_packet, offset, size_of_data_left_to_transmit;
		bool first;
		char data[DATA_PER_FULL_PACKET * sizeof(uint32_t)];
		unsigned char miss_seq;
		uint32_t n_packets, i, datasize;

		//Calculate number of missing sequences based on difference between expected and received
		uint32_t  miss_dim = this->max_seq_num - received_seq_nums->size();

		uint32_t *missing_seq = new uint32_t[miss_dim];
		int j = 0;

		// Calculate missing sequence numbers and add them to "missing"
		for(i = 0 ; i < this->max_seq_num; i++) {

			if(received_seq_nums->find(i) == received_seq_nums->end()) {

				//missing is only used for statistical purposes
				//missing.push_back(i);
				missing_seq[j++] = i;
			}
		}

		//Set correct number of lost sequences
		miss_dim = (uint32_t)j;

		//No missing sequences
		if(miss_dim == 0)
			return true;

		n_packets = 1;
		length_via_format2 = miss_dim - (DATA_PER_FULL_PACKET - 2);

		if(length_via_format2 > 0)
			n_packets += (uint32_t)ceil((float)(length_via_format2)/(float)(DATA_PER_FULL_PACKET - 1));

		// Transmit missing sequences as a new SDP Packet
		first = true;
		seq_num_offset = 0;

		for(i = 0 ; i < n_packets ; i++) {

			length_left_in_packet = DATA_PER_FULL_PACKET;
			offset = 0;

			// If first, add n packets to list
			if(first) {

				// Get left over space / data size
				size_of_data_left_to_transmit = min(length_left_in_packet - 2, (int)(miss_dim)-seq_num_offset);

				datasize = (size_of_data_left_to_transmit + 2) * sizeof(uint32_t);

				// Pack flag and n packets
				memcpy(data, &SDP_PACKET_START_MISSING_SEQ_COMMAND_ID, sizeof(uint32_t));
				memcpy(data+sizeof(uint32_t), &n_packets, sizeof(uint32_t));

				// Update state
				offset += 2*sizeof(uint32_t);
				length_left_in_packet -= 2;
				first = false;
			}
			// Just add data
			else {

				// Get left over space / data size
				size_of_data_left_to_transmit = min(DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM, (int)miss_dim-seq_num_offset);

				datasize = (size_of_data_left_to_transmit + 1) * sizeof(uint32_t);

				// Pack flag
				memcpy(data+offset, &SDP_PACKET_MISSING_SEQ_COMMAND_ID, sizeof(uint32_t));

				offset += sizeof(uint32_t);
				length_left_in_packet -= 1;
			}

			//Data in vector is contiguous(defined as c++ specification), verify only that offset and size to be transmitted are correct
			memcpy(data+offset, missing_seq+seq_num_offset, size_of_data_left_to_transmit*sizeof(uint32_t));

			seq_num_offset += length_left_in_packet;

			SDPMessage message = SDPMessage(
			        this->placement_x, this->placement_y, this->placement_p, this->port_connection,
			        SDPMessage::REPLY_NOT_EXPECTED, 255, 255, 255, 0, 0, data,
			        datasize);

			sender->send_data(message.convert_to_byte_array(), message.length_in_bytes());

			usleep(TIMEOUT_PER_SENDING_IN_MICROSECONDS);
		}

		return false;
}


//Function for computing expected maximum number of packets
uint32_t host_data_receiver::calculate_max_seq_num(uint32_t length) {

	int n_sequence_number;
	unsigned long data_left;
	float extra_n_sequences;

	n_sequence_number = 0;

	extra_n_sequences = (float)length / (float)(DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM * WORD_TO_BYTE_CONVERTER);

	n_sequence_number += ceil(extra_n_sequences);

	return (uint32_t)n_sequence_number;
}


//Function for checking that all packets have been received
bool host_data_receiver::check(set<uint32_t> *received_seq_nums, uint32_t max_needed) {

	uint32_t recvsize = received_seq_nums->size();

	if(recvsize > (max_needed + 1)) {

		throw "Received more data than expected";
	}
	if(recvsize != (max_needed + 1)) {

		return false;
	}
	return true;
}


// Function for processing each received packet and checking end of transmission
void host_data_receiver::process_data(UDPConnection *sender, bool *finished, 
										set<uint32_t> *received_seq_nums, char *recvdata, int datalen) {

	int length_of_data, i, j;
	uint32_t last_mc_packet, first_packet_element, offset, true_data_length, seq_num;
	bool is_end_of_stream;

	//Data size of the packet
	length_of_data = datalen;

	memcpy(&first_packet_element, recvdata, sizeof(uint32_t));

	seq_num = first_packet_element & 0x7FFFFFFF;

	is_end_of_stream = ((first_packet_element & LAST_MESSAGE_FLAG_BIT_MASK) != 0) ? true : false;

	if(seq_num > this->max_seq_num) {

		throw "Got insane sequence number";
	}

	offset = (seq_num) * DATA_PER_FULL_PACKET_WITH_SEQUENCE_NUM * WORD_TO_BYTE_CONVERTER;

	true_data_length = (offset + length_of_data - SEQUENCE_NUMBER_SIZE);

	if(is_end_of_stream && length_of_data == END_FLAG_SIZE_IN_BYTES) {


	}
	else {

		memcpy(buffer+offset, recvdata+SEQUENCE_NUMBER_SIZE, (true_data_length-offset));
	}

	received_seq_nums->insert(seq_num);

	if(is_end_of_stream) {

		if(!check(received_seq_nums, this->max_seq_num)) {

			*finished = retransmit_missing_sequences(sender, received_seq_nums);
		}
		else {

			*finished = true;
		}
	}

}

void host_data_receiver::reader_thread(UDPConnection *receiver) {

	char data[400];
	int recvd;
	packet p;

	// While socket is open add messages to the queue
	do {

		try {

			recvd = receiver->receive_data(data, 400);

			memcpy(p.content, data, recvd*sizeof(char));
			p.size = recvd;

		} catch(char const *e) {

			this->rdr.thrown = true;
			this->rdr.val = e;
			return;
		}

		if(recvd)
			messqueue->push(p);

		//If the other thread trew an exception(no need for mutex, in the worst case this thread will add an additional value to the queue)
		if(this->pcr.thrown == true)
			return;

	}while(recvd);
}

void host_data_receiver::processor_thread(UDPConnection *sender) {

	char data[400];
	int receivd = 0, timeoutcount = 0, datalen;
	bool finished = false;
	set<uint32_t> *received_seq_nums = new set<uint32_t>;
	packet p;

	while(!finished) {

		try {

		 	p = messqueue->pop();

		 	memcpy(data, p.content, p.size*sizeof(char));
		 	datalen = p.size;


		 	process_data(sender, &finished, received_seq_nums, data, datalen);

		 }catch(TimeoutQueueException e) {

		 	if (timeoutcount > TIMEOUT_RETRY_LIMIT) {

				this->pcr.thrown = true;
				this->pcr.val = "Failed to hear from the machine. Please try removing firewalls";

			}

		 	timeoutcount++;

		 	if(!finished) {

					// retransmit missing packets
					finished = retransmit_missing_sequences(sender, received_seq_nums);
			}


		 }catch(const char *e) {

		 	this->pcr.thrown = true;
			this->pcr.val = e;
			delete sender;
			return;
		 }

		 if(this->rdr.thrown == true)
		 	return;
	}

	// close socket and inform the reader that transmission is completed
	delete sender;
	this->finished = true;
}

// Function externally callable for data gathering. It returns a buffer containing read data
char * host_data_receiver::get_data() {

	int datalen, timeoutcount;
	double seconds_taken;

	try {

		// create connection
		UDPConnection *sender =  new UDPConnection(NULL, NULL, 17893, this->hostname);

		// send the initial command to start data transmission
		send_initial_command(sender, sender);

		//pthread_create(&reader, NULL, &host_data_receiver::reader_thread, (void *) sender);
		//pthread_create(&processor, NULL, &host_data_receiver::processor_thread, (void *) sender);

		//pthread_join(reader, NULL);
		//pthread_join(processor, NULL);

		thread reader(&host_data_receiver::reader_thread, this, sender);
		thread processor(&host_data_receiver::processor_thread, this, sender);

		reader.join();
		processor.join();

		if(this->pcr.thrown == true) {

			cout << this->pcr.val << endl;
			return NULL;
		} 
		else if(this->rdr.thrown == true && this->finished == false) {

			cout << this->rdr.val << endl;
			return NULL;
		}


	}catch(char const *e) {

		cout << e << endl;

		return NULL;
	}

	return this->buffer;
}

/*
//Same behavior of get_data() function, but returns a valid type for python code
py::bytes host_data_receiver::get_data_for_python(char *hostname, int port_connection, int placement_x, int placement_y, int placement_p,
				int length_in_bytes, int memory_address, int chip_x, int chip_y, int iptag) {

	bool finished;
	char data[400];
	int datalen, timeoutcount;
	uint32_t seq_num, max_seq_num, length;
	set<uint32_t> *received_seq_nums = new set<uint32_t>;
	time_t start, end;
	double seconds_taken;
	char *buffer;

	finished = false;
	seq_num = 1;
	max_seq_num = 0;
	length = 0;

	time(&start);

	try {

		// create connection
		UDPConnection *sender =  new UDPConnection(NULL, NULL, 17893, hostname);

		// send the initial command to start data transmission
		send_initial_command(sender, placement_x, placement_y, placement_p, port_connection, (uint32_t)length_in_bytes, (uint32_t)memory_address, chip_x, chip_y, iptag, sender);

		buffer = new char[length_in_bytes];

		max_seq_num = calculate_max_seq_num(length_in_bytes);

		while(!finished) {

			try {
				// receive data
				datalen = sender->receive_data(data, 400, TIMEOUT_PER_RECEIVE_IN_SECONDS, 0);

				timeoutcount = 0;

				// process received data
	        		process_data(
	        					 sender, &finished, &seq_num, received_seq_nums, data, port_connection,
							 placement_x, placement_y, placement_p, buffer, &max_seq_num, datalen, &length);

			}catch(TimeoutException e) {

				if (timeoutcount > TIMEOUT_RETRY_LIMIT) {

					throw "Failed to hear from the machine. Please try removing firewalls";
				}
				timeoutcount++;

				//delete sender;

				//uint32_t loc_port = sender->get_local_port();

				//sender = new UDPConnection(loc_port, NULL, 17893, hostname);

				if(!finished) {

					// retransmit missing packets
					finished = retransmit_missing_sequences(
							sender, received_seq_nums, placement_x, placement_y,
							placement_p, port_connection, max_seq_num);
				}
			}
		}
	}catch(char const *e) {

		cout << e << endl;
		//This will cause the simulation to fail, otherwise it will get wrong data!
		return NULL;
	}

	time(&end);

	seconds_taken = difftime(end, start);

	std::string *str = new string((const char *)buffer, length_in_bytes);

	return py::bytes(*str);
}*/


// Function externally callable for data gathering. It can be called by multiple threads simultaneously
void host_data_receiver::get_data_threadable(char *filepath_read, char *filepath_missing) {

	FILE *fp1, *fp2;

	get_data();

	fp1 = fopen(filepath_read, "wb");
	//fp2 = fopen(filepath_missing, "w");

	fwrite(this->buffer, sizeof(char), length_in_bytes, fp1);

	/*vector<uint32_t>::iterator i;
	char *miss = new char[sizeof(uint32_t) * missing.size()];
	int offset = 0;

	for(i = missing.begin() ; i != missing.end() ; i++) {

		uint32_t v = (uint32_t)*i;
		fprintf(fp2, "%u\n", v);
	}*/

	fclose(fp1);
	//fclose(fp2);

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
