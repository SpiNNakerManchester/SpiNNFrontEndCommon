#include "SDPHeader.h"

SDPHeader::SDPHeader(int destination_chip_x, int destination_chip_y,
                int destination_chip_p, int destination_port, int flags, int tag, 
                int source_port, int source_cpu, int source_chip_x, int source_chip_y){

	this->destination_chip_x = (uint8_t) destination_chip_x;
	this->destination_chip_y = (uint8_t) destination_chip_y;
    this->destination_chip_p = (uint8_t) destination_chip_p;
    this->destination_port = (uint8_t) destination_port;
    this->flags = (uint8_t) flags;
    this->tag = (uint8_t) tag;
    this->source_port = (uint8_t) source_port;
    this->source_cpu = (uint8_t) source_cpu;
    this->source_chip_x = (uint8_t) source_chip_x;
    this->source_chip_y = (uint8_t) source_chip_y;
    this->length = 10 * sizeof(uint8_t);
}


char * SDPHeader::convert_byte_array(){

	uint8_t tmp;
    uint8_t *a;

    char * message_data = (char *)malloc(this->length);

    //Build SDP Header
    //Flags - Tags - Dest_port+cpu - Source_port+cpu - Dest_chip_y - Dest_chip_x - Source_chip_y - Source_chip_x

    tmp = 0;

    memcpy(message_data, &tmp, sizeof(uint8_t));

    memcpy(message_data+sizeof(uint8_t), &tmp, sizeof(uint8_t));
    memcpy(message_data+2*sizeof(uint8_t), &this->flags, sizeof(uint8_t));
    memcpy(message_data+3*sizeof(uint8_t), &this->tag, sizeof(uint8_t));

    //Compose  Dest_port+cpu = 3 MSBs as port and 5 LSBs as cpu
    tmp = ((this->destination_port & 7) << 5) | (this->destination_chip_p & 31);
    memcpy(message_data+4*sizeof(uint8_t), &tmp, sizeof(uint8_t));

    //Compose  Source_port+cpu = 3 MSBs as port and 5 LSBs as cpu
    tmp = ((this->source_port & 7) << 5) | (this->source_cpu & 31);
    memcpy(message_data+5*sizeof(uint8_t), &tmp, sizeof(uint8_t));

    memcpy(message_data+6*sizeof(uint8_t), &this->destination_chip_y, sizeof(uint8_t));
    memcpy(message_data+7*sizeof(uint8_t), &this->destination_chip_x, sizeof(uint8_t));
    memcpy(message_data+8*sizeof(uint8_t), &this->source_chip_y, sizeof(uint8_t));
    memcpy(message_data+9*sizeof(uint8_t), &this->source_chip_x, sizeof(uint8_t));

    return message_data;
}

int SDPHeader::length_bytes(){
    return this->length;
}

