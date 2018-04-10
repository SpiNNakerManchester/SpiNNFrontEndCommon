#ifndef _SDPMESSAGE_
#define _SDPMESSAGE_

#include "SDPHeader.h"
#include <vector>

/// Describes an SDP message
class SDPMessage {
public:
    static constexpr int MAX_PACKET_SIZE = 300;
    static constexpr int MAX_PACKET_SIZE_DATA = 292;
    static constexpr int REPLY_NOT_EXPECTED = 0x07;
    static constexpr int REPLY_EXPECTED = 0x87;

private:
    /// The data in the message
    const void *data;
    /// How long the data is
    const int data_length;
    /// The SDP header for the message
    const SDPHeader header;

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
	    const void *data, ///< [in] Payload
	    int length) :     ///< [in] Payload size
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
	    const std::vector<uint8_t> &data) : ///< [in] Payload
	    data(data.data()), data_length(data.size()), header(
		    destination_chip_x, destination_chip_y,
		    destination_chip_p, destination_port, flags, tag,
		    source_port, source_cpu, source_chip_x, source_chip_y)
    {
    }

    /// Get the overall size of the message.
    int length_in_bytes() const
    {
	return data_length + header.length_bytes();
    }

    /// Write the message into a buffer (for sending).
    void convert_to_byte_vector(std::vector<uint8_t> &data) const;
};

#endif
