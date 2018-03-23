#ifndef _SDPHEADER_
#define _SDPHEADER_

#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <cstdint>

class SDPHeader{

	public:
		SDPHeader(int destination_chip_x, int destination_chip_y,
        		int destination_chip_p, int destination_port, int flags, int tag, 
        		int source_port, int source_cpu, int source_chip_x, int source_chip_y);
		//~SDPHeader();

		char * convert_byte_array();
		int length_bytes();

	private:
		int destination_chip_x;
    		uint8_t destination_chip_y;
    		uint8_t destination_chip_p;
    		uint8_t destination_port;
    		uint8_t flags;
    		uint8_t length;
    		uint8_t tag;
    		uint8_t source_port;
    		uint8_t source_cpu;
    		uint8_t source_chip_x;
    		uint8_t source_chip_y;

};

#endif

