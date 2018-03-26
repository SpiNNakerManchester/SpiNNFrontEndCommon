#include "SDPMessage.h"

void SDPMessage::convert_to_byte_vector(std::vector<uint8_t> &buffer)
{
    buffer.resize(length_in_bytes());
    header.write_header(buffer);
    memcpy(((char *) buffer.data()) + header.length_bytes(),
	    data, data_length);
}
