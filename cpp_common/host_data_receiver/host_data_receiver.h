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

#if 0
//#include <pybind11/pybind11.h>
#endif

#include "../common/SDPHeader.h"
#include "../common/SDPMessage.h"
#include "../common/UDPConnection.h"
#include "PQueue.h"

class host_data_receiver {
public:
    static const int SET_IP_TAG = 26;

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
            int iptag);
    const uint8_t *get_data();
    void get_data_threadable(
	    const char *filepath_read, const char *filepath_missing);
#if 0
    pybind11::bytes get_data_for_python(
	    char *hostname, int port_connection, int placement_x,
	    int placement_y, int placement_p, int length_in_bytes,
	    int memory_address, int chip_x, int chip_y, int iptag);
#endif

private:
    void send_initial_command(UDPConnection &sender, UDPConnection &receiver);
    void receive_message(UDPConnection &receiver, vector<uint8_t> &buffer);
    bool retransmit_missing_sequences(
            UDPConnection &sender, set<uint32_t> &received_seq_nums);
    uint32_t calculate_max_seq_num(uint32_t length);
    bool check(set<uint32_t> &received_seq_nums, uint32_t max_needed);
    void process_data(
            UDPConnection &sender, bool &finished,
            set<uint32_t> &received_seq_nums, vector<uint8_t> &recvdata);
    void reader_thread(UDPConnection *receiver);
    void processor_thread(UDPConnection *sender);

    //Used to verify if one of the thread threw any exception
    struct thexc {
        const char *val;
        volatile bool thrown;
    };

    int port_connection;
    int placement_x;
    int placement_y;
    int placement_p;
    string hostname;
    uint32_t length_in_bytes;
    uint32_t memory_address;
    int chip_x;
    int chip_y;
    int iptag;
    PQueue<vector<uint8_t>> messqueue;
    vector<uint8_t> buffer;
    uint32_t max_seq_num;
    thexc rdr, pcr;
    bool finished;
};

#endif
