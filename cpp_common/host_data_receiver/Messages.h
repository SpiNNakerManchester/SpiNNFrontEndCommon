/*
 * Messages for the host_data_receiver
 */

#ifndef HDR_MESSAGES_H
#define HDR_MESSAGES_H

#include <cstdint>
#include <SDPMessage.h>
#include "host_data_receiver.h"

//Constants
static constexpr uint32_t WORDS_PER_PACKET = 68;

class OneWayMessage: public SDPMessage {
public:
    OneWayMessage(int x, int y, int p, int port, void *data, int length) :
	    SDPMessage(x, y, p, port, SDPMessage::REPLY_NOT_EXPECTED, 255,
		    255, 255, 0, 0, data, length)
    {
    }
};

class TwoWayMessage: public SDPMessage {
public:
    TwoWayMessage(int x, int y, int p, int port, void *data, int length) :
	    SDPMessage(x, y, p, port, SDPMessage::REPLY_EXPECTED, 255,
		    255, 255, 0, 0, data, length)
    {
    }
};

class SetIPTagMessage: public TwoWayMessage {
public:
    SetIPTagMessage(
	    int chip_x,
	    int chip_y,
	    int iptag,
	    uint32_t target_ip,
	    uint32_t target_port) :
	    TwoWayMessage(chip_x, chip_y, 0, 0, &payload, sizeof(payload))
    {
	payload.cmd = host_data_receiver::SET_IP_TAG;
	payload.seq = 0;
	int strip_sdp = 1;
	payload.packed = (strip_sdp << 28) | (1 << 16) | iptag;
	payload.port = target_port;
	payload.ip = target_ip;
    }
private:
    struct SCP_SetIPTag_Payload {
	uint16_t cmd;
	uint16_t seq;
	uint32_t packed;
	uint32_t port;
	uint32_t ip;
    } payload;
};

class StartSendingMessage: public OneWayMessage {
public:
    static constexpr uint32_t SDP_PACKET_START_SENDING_COMMAND_ID = 100;
    StartSendingMessage(
	    int x,
	    int y,
	    int p,
	    int port,
	    uint32_t address,
	    uint32_t length) :
	    OneWayMessage(x, y, p, port, (char *) &payload, sizeof(payload))
    {
	payload.cmd = make_word_for_buffer(SDP_PACKET_START_SENDING_COMMAND_ID);
	payload.address = make_word_for_buffer(address);
	payload.length = make_word_for_buffer(length);
    }
private:
    struct Payload {
	uint32_t cmd;
	uint32_t address;
	uint32_t length;
    } payload;
};

class FirstMissingSeqsMessage: public OneWayMessage {
public:
    static constexpr uint32_t SDP_PACKET_START_MISSING_SEQ_COMMAND_ID = 1000;
    static constexpr uint32_t const& PAYLOAD_SIZE = WORDS_PER_PACKET - 2;
    FirstMissingSeqsMessage(
	    int x,
	    int y,
	    int p,
	    int port,
	    const uint32_t *data,
	    uint32_t length,
	    uint32_t num_packets) :
	    OneWayMessage(x, y, p, port, buffer,
		    (length + 2) * sizeof(uint32_t))
    {
	buffer[0] = make_word_for_buffer(
		SDP_PACKET_START_MISSING_SEQ_COMMAND_ID);
	buffer[1] = make_word_for_buffer(num_packets);
	memcpy(&buffer[2], data, length * sizeof(uint32_t));
    }
private:
    uint32_t buffer[WORDS_PER_PACKET];
};

class MoreMissingSeqsMessage: public OneWayMessage {
public:
    static constexpr uint32_t SDP_PACKET_MISSING_SEQ_COMMAND_ID = 1001;
    static constexpr uint32_t const& PAYLOAD_SIZE = WORDS_PER_PACKET - 1;
    MoreMissingSeqsMessage(
	    int x,
	    int y,
	    int p,
	    int port,
	    const uint32_t *data,
	    uint32_t length) :
	    OneWayMessage(x, y, p, port, buffer,
		    (length + 1) * sizeof(uint32_t))
    {
	buffer[0] = make_word_for_buffer(SDP_PACKET_MISSING_SEQ_COMMAND_ID);
	memcpy(&buffer[1], data, length * sizeof(uint32_t));
    }
private:
    uint32_t buffer[WORDS_PER_PACKET];
};

#endif // HDR_MESSAGES_H
