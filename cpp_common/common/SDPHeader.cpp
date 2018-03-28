#include "SDPHeader.h"

static inline uint8_t pack(uint8_t port, uint8_t processor)
{
    // Layout in returned byte:
    //
    // [7][6][5][4][3][2][1][0]
    //  ^^^^^^^  ^^^^^^^^^^^^^
    //    port     processor
    return ((port & 0x07) << 5) | (processor & 0x1F);
}

// ASSUME WE HAVE ENOUGH SPACE!
void SDPHeader::write_header(std::vector<uint8_t> &data)
{
    //Build SDP Header
    //Flags - Tags - Dest_port+cpu - Source_port+cpu - Dest_chip_y -
    //Dest_chip_x - Source_chip_y - Source_chip_x

    data[0] = 0;
    data[1] = 0;
    data[2] = flags;
    data[3] = tag;
    data[4] = pack(destination_port, destination_chip_p);
    data[5] = pack(source_port, source_cpu);
    data[6] = destination_chip_y;
    data[7] = destination_chip_x;
    data[8] = source_chip_y;
    data[9] = source_chip_x;
}
