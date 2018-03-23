#ifndef _SDPMESSAGE_
#define _SDPMESSAGE_

#include "SDPHeader.h"

class SDPMessage{

    public:
        SDPMessage(int destination_chip_x, int destination_chip_y,
                int destination_chip_p, int destination_port, int flags,
                int tag, int source_port, int source_cpu, int source_chip_x,
                int source_chip_y, char * data, int length);
        //~SDPMessage();

        char * convert_to_byte_array();
        int length_in_bytes();
        static const int MAX_PACKET_SIZE = 300;
        static const int MAX_PACKET_SIZE_DATA = 292;
        static const int REPLY_NOT_EXPECTED = 0x07;
        static const int REPLY_EXPECTED = 0x87;

    private:
        char * data;
        SDPHeader * header;
        int data_length;


};

#endif

