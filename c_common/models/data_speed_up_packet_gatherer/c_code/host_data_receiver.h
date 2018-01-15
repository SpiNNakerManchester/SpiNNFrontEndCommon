#ifndef _HOST_DATA_RECEIVER_
#define _HOST_DATA_RECEIVER_

#include <stdio.h>
#include <stdlib.h>
#include <string>
#include <unistd.h>
#include <math.h>
#include <iostream>
#include <algorithm>
#include <vector>
#include <set>
#include <ctime>
#include <cstdint>
#include <thread>
//#include <pybind11/pybind11.h>

#include "SDPHeader.h"
#include "SDPMessage.h"
#include "UDPConnection.h"
#include "PQueue.h"


class host_data_receiver {

	public:
		host_data_receiver(int port_connection, int placement_x, int placement_y, int placement_p,
						   char *hostname, int length_in_bytes, int memory_address, int chip_x, int chip_y, int iptag);
		char * get_data();
		void get_data_threadable(char *filepath_read, char *filepath_missing);
		//pybind11::bytes get_data_for_python(char *hostname, int port_connection, int placement_x, int placement_y, int placement_p,
		//		int length_in_bytes, int memory_address, int chip_x, int chip_y, int iptag);

	private:
		char * build_scp_req(uint16_t cmd, uint32_t port, int strip_sdp, uint32_t ip_address);
		void send_initial_command(UDPConnection *sender, UDPConnection *receiver);
        bool retransmit_missing_sequences(UDPConnection *sender, set<uint32_t> *received_seq_nums);
        uint32_t calculate_max_seq_num(uint32_t length);
        bool check(set<uint32_t> *received_seq_nums, uint32_t max_needed);
        void process_data(UDPConnection *sender, bool *finished, set<uint32_t> *received_seq_nums, char *recvdata, int datalen);
        void reader_thread(UDPConnection *receiver);
        void processor_thread(UDPConnection *sender);

        typedef struct packet{

			char content[400];
			int size;

		}packet;

		//Used to verify if one of the thread threw any exception
		typedef struct thexc {

			const char *val;
			bool thrown;

		}thexc;

        int port_connection;
		int placement_x;
		int placement_y;
		int placement_p;
		char *hostname;
		uint32_t length_in_bytes;
		uint32_t memory_address;
		int chip_x;
		int chip_y;
		int iptag;
		PQueue<packet> *messqueue;
		char *buffer;
		uint32_t max_seq_num;
		thexc rdr;
		thexc pcr;


};

#endif