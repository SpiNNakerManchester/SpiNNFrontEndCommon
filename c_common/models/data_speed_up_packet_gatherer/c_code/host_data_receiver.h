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
//#include <pybind11/pybind11.h>

#include "SDPHeader.h"
#include "SDPMessage.h"
#include "UDPConnection.h"


class host_data_receiver {

	public:
		host_data_receiver();
		char * get_data(char *hostname, int port_connection, int placement_x, int placement_y, int placement_p,
						int length_in_bytes, int memory_address, int chip_x, int chip_y, int iptag);
		void get_data_threadable(char *hostname, int port_connection, int placement_x, int placement_y,
								int placement_p, char *filepath_read, char *filepath_missing, int length_in_bytes,
								int memory_address, int chip_x, int chip_y, int iptag);
		//pybind11::bytes get_data_for_python(char *hostname, int port_connection, int placement_x, int placement_y, int placement_p,
		//		int length_in_bytes, int memory_address, int chip_x, int chip_y, int iptag);

	private:
		char * build_scp_req(uint16_t cmd, uint32_t port, int iptag, int strip_sdp, uint32_t ip_address);
		void send_initial_command(UDPConnection *sender,  int placement_x, int placement_y,
        						int placement_p, int port_connection, uint32_t length_in_bytes,
        						uint32_t memory_address, int chip_x, int chip_y, int iptag, UDPConnection *receiver);
        bool retransmit_missing_sequences(UDPConnection *sender, set<uint32_t> *received_seq_nums, int placement_x,
										int placement_y, int placement_p, int port_connection, uint32_t max_seq_num);
        uint32_t calculate_max_seq_num(uint32_t length);
        bool check(set<uint32_t> *received_seq_nums, uint32_t max_needed);
        void process_data(UDPConnection *sender, bool *finished, uint32_t *seq_num,
						set<uint32_t> *received_seq_nums, char *recvdata, int port_connection,
						int placement_x, int placement_y, int placement_p, char *buffer,
						uint32_t *max_seq_num, int datalen, uint32_t *length);

        vector<uint32_t> missing;
};

#endif