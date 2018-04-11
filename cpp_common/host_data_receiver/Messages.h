/*
 * Messages for the host_data_receiver
 */

#ifndef HDR_MESSAGES_H
#define HDR_MESSAGES_H

#include <cstdint>
#include <SDPMessage.h>
#include "host_data_receiver.h"

// NASTY HACK for bug in older GCC
#if defined(__GNUC__) && !defined(__clang__) && __GNUC__ < 5
#define CONSTREF
#define CONSTDEF(type, name)  constexpr type name
#else
#define CONSTREF              const&
#define CONSTDEF(type, name)
#endif

//Constants
static constexpr uint32_t WORDS_PER_PACKET = 68;

/// Basic SDP message that does not want an acknowledgement
class OneWayMessage: public SDPMessage {
public:
    OneWayMessage(int x, int y, int p, int port, void *data, int length) :
	    SDPMessage(x, y, p, port, SDPMessage::REPLY_NOT_EXPECTED, 255,
		    255, 255, 0, 0, data, length)
    {
    }
};

/// Basic SDP message that wants an acknowledgement
class TwoWayMessage: public SDPMessage {
public:
    TwoWayMessage(int x, int y, int p, int port, void *data, int length) :
	    SDPMessage(x, y, p, port, SDPMessage::REPLY_EXPECTED, 255,
		    255, 255, 0, 0, data, length)
    {
    }
};

/// SDP message that configures an IP Tag
class SetIPTagMessage: public TwoWayMessage {
public:
    SetIPTagMessage(
	    int chip_x, ///< [in] The ethernet chip X coordinate
	    int chip_y, ///< [in] The ethernet chip Y coordinate
	    int iptag, ///< [in] The IP Tag to set
	    uint32_t target_ip, ///< [in] The target IP address of the tag
	    uint32_t target_port) : ///< [in] The target UDP port of the tag
	    TwoWayMessage(chip_x, chip_y, 0, 0, &payload, sizeof(payload))
    {
	// TODO: Make this endian-aware
	payload.cmd = host_data_receiver::SET_IP_TAG;
	payload.seq = 0;
	int strip_sdp = 1;
	payload.packed = (strip_sdp << 28) | (1 << 16) | iptag;
	payload.port = target_port;
	payload.ip = target_ip;
    }
private:
    /// Space for assembling the message payload
    struct SCP_SetIPTag_Payload {
	uint16_t cmd;
	uint16_t seq;
	uint32_t packed;
	uint32_t port;
	uint32_t ip;
    } payload;
};

/// SDP message that starts a data transfer.
class StartSendingMessage: public OneWayMessage {
    /// The command ID of the message
    static constexpr uint32_t SDP_PACKET_START_SENDING_COMMAND_ID = 100;
public:
    StartSendingMessage(
	    int x, ///< [in] Where to send the message to (X coord)
	    int y, ///< [in] Where to send the message to (Y coord)
	    int p, ///< [in] Where to send the message to (P coord)
	    int port, ///< [in] Which UDP port to send the message to
	    uint32_t address, ///< [in] Where to read from?
	    uint32_t length) : ///< [in] How much data to read?
	    OneWayMessage(x, y, p, port, (char *) &payload, sizeof(payload))
    {
	payload.cmd = make_word_for_buffer(SDP_PACKET_START_SENDING_COMMAND_ID);
	payload.address = make_word_for_buffer(address);
	payload.length = make_word_for_buffer(length);
    }
private:
    /// Space for assembling the message payload
    struct Payload {
	uint32_t cmd;
	uint32_t address;
	uint32_t length;
    } payload;
};

/// SDP message that starts reporting missing sequence numbers so they
/// can be retransmitted.
class FirstMissingSeqsMessage: public OneWayMessage {
    /// The command ID of the message
    static constexpr uint32_t SDP_PACKET_START_MISSING_SEQ_COMMAND_ID = 1000;
public:
    /// How many words of payload can this message contain?
    static constexpr uint32_t CONSTREF PAYLOAD_SIZE = WORDS_PER_PACKET - 2;
    FirstMissingSeqsMessage(
	    int x, ///< [in] Where to send the message to (X coord)
	    int y, ///< [in] Where to send the message to (Y coord)
	    int p, ///< [in] Where to send the message to (P coord)
	    int port, ///< [in] Which UDP port to send the message to
	    const uint32_t *data, ///< [in] The array of missing sequence numbers
	    uint32_t length, ///< [in] How many to send this time
	    uint32_t num_packets) : ///< [in] Number of packets being sent
	    OneWayMessage(x, y, p, port, buffer,
		    (length + 2) * sizeof(uint32_t))
    {
	buffer[0] = make_word_for_buffer(
		SDP_PACKET_START_MISSING_SEQ_COMMAND_ID);
	buffer[1] = make_word_for_buffer(num_packets);
	memcpy(&buffer[2], data, length * sizeof(uint32_t));
    }
private:
    /// Space for assembling the message payload
    uint32_t buffer[WORDS_PER_PACKET];
};

/// SDP message that reports further missing sequence numbers so they
/// can be retransmitted.
class MoreMissingSeqsMessage: public OneWayMessage {
    /// The command ID of the message
    static constexpr uint32_t SDP_PACKET_MISSING_SEQ_COMMAND_ID = 1001;
public:
    /// How many words of payload can this message contain?
    static constexpr uint32_t CONSTREF PAYLOAD_SIZE = WORDS_PER_PACKET - 1;

    MoreMissingSeqsMessage(
	    int x, ///< [in] Where to send the message to (X coord)
	    int y, ///< [in] Where to send the message to (Y coord)
	    int p, ///< [in] Where to send the message to (P coord)
	    int port, ///< [in] Which UDP port to send the message to
	    const uint32_t *data, ///< [in] The array of missing sequence numbers
	    uint32_t length) : ///< [in] How many to send this time
	    OneWayMessage(x, y, p, port, buffer,
		    (length + 1) * sizeof(uint32_t))
    {
	buffer[0] = make_word_for_buffer(SDP_PACKET_MISSING_SEQ_COMMAND_ID);
	memcpy(&buffer[1], data, length * sizeof(uint32_t));
    }
private:
    /// Space for assembling the message payload
    uint32_t buffer[WORDS_PER_PACKET];
};

CONSTDEF(uint32_t, FirstMissingSeqsMessage::PAYLOAD_SIZE);
CONSTDEF(uint32_t, MoreMissingSeqsMessage::PAYLOAD_SIZE);

#endif // HDR_MESSAGES_H
