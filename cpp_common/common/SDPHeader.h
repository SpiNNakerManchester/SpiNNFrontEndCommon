#ifndef _SDPHEADER_
#define _SDPHEADER_

#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <cstdint>
#include <vector>

/// The header for an SDP message
class SDPHeader {
private:
    const uint8_t destination_chip_x;
    const uint8_t destination_chip_y;
    const uint8_t destination_chip_p;
    const uint8_t destination_port;
    const uint8_t flags;
    const uint8_t length;
    const uint8_t tag;
    const uint8_t source_port;
    const uint8_t source_cpu;
    const uint8_t source_chip_x;
    const uint8_t source_chip_y;

public:
    SDPHeader(
	    int destination_chip_x,
	    int destination_chip_y,
	    int destination_chip_p,
	    int destination_port,
	    int flags,
	    int tag,
	    int source_port,
	    int source_cpu,
	    int source_chip_x,
	    int source_chip_y) :
	    destination_chip_x((uint8_t) destination_chip_x),
	    destination_chip_y((uint8_t) destination_chip_y),
	    destination_chip_p((uint8_t) destination_chip_p),
	    destination_port((uint8_t) destination_port),
	    flags((uint8_t) flags),
	    length((uint8_t) 10),
	    tag((uint8_t) tag),
	    source_port((uint8_t) source_port),
	    source_cpu((uint8_t) source_cpu),
	    source_chip_x((uint8_t) source_chip_x),
	    source_chip_y((uint8_t) source_chip_y)
    {
    }

    /// Get the length of the header
    int length_bytes() const
    {
	return length * sizeof(uint8_t);
    }

    /// Write the header into a buffer (for sending)
    void write_header(std::vector<uint8_t> &data) const;
};

#endif
