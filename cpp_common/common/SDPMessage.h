#ifndef _SDPMESSAGE_
#define _SDPMESSAGE_

#include "SDPHeader.h"
#include <vector>

class SDPMessage {
public:
    static const int MAX_PACKET_SIZE = 300;
    static const int MAX_PACKET_SIZE_DATA = 292;
    static const int REPLY_NOT_EXPECTED = 0x07;
    static const int REPLY_EXPECTED = 0x87;

private:
    const char *data;
    const int data_length;
    SDPHeader header;

public:
    SDPMessage(
	    int destination_chip_x,
	    int destination_chip_y,
	    int destination_chip_p,
	    int destination_port,
	    int flags,
	    int tag,
	    int source_port,
	    int source_cpu,
	    int source_chip_x,
	    int source_chip_y,
	    char *data,
	    int length) :
	    data(data), data_length(length), header(destination_chip_x,
		    destination_chip_y, destination_chip_p, destination_port,
		    flags, tag, source_port, source_cpu, source_chip_x,
		    source_chip_y)
    {
    }
    SDPMessage(
	    int destination_chip_x,
	    int destination_chip_y,
	    int destination_chip_p,
	    int destination_port,
	    int flags,
	    int tag,
	    int source_port,
	    int source_cpu,
	    int source_chip_x,
	    int source_chip_y,
	    const std::vector<uint8_t> &data) :
	    data((const char *) data.data()), data_length(data.size()),
	    header(destination_chip_x,
		    destination_chip_y, destination_chip_p, destination_port,
		    flags, tag, source_port, source_cpu, source_chip_x,
		    source_chip_y)
    {
    }

    int length_in_bytes() {
        return data_length + header.length_bytes();
    }

    void convert_to_byte_vector(std::vector<uint8_t> &data);
};

#endif
