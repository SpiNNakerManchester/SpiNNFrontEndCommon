#include "SDPMessage.h"

SDPMessage::SDPMessage(int destination_chip_x, int destination_chip_y,
                   int destination_chip_p, int destination_port, int flags,
                   int tag, int source_port, int source_cpu, int source_chip_x,
                   int source_chip_y, char * data, int length){

    this->data = data;

    this->data_length = length;

    this->header = (SDPHeader *) malloc(sizeof(SDPHeader));

    *(this->header) = SDPHeader(destination_chip_x, destination_chip_y, destination_chip_p,
                             destination_port, flags, tag, source_port, source_cpu, source_chip_x,
                             source_chip_y);

}

char * SDPMessage::convert_to_byte_array(){

    char * message_data = (char *)malloc(this->length_in_bytes());
    memcpy(message_data, this->header->convert_byte_array(), this->header->length_bytes()); 

    memcpy(message_data+this->header->length_bytes(), this->data, this->data_length);

    return message_data;
}

int SDPMessage::length_in_bytes(){
    return this->data_length + this->header->length_bytes();
}


