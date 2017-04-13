#ifndef _EIEIO_STRUCTURES_H
#define _EIEIO_STRUCTURES_H

//! The EIEIO message types

typedef enum eieio_data_message_types {
    KEY_16_BIT = 0,
    KEY_PAYLOAD_16_BIT = 1,
    KEY_32_BIT = 2,
    KEY_PAYLOAD_32_BIT = 3
} eieio_data_message_types;

// The meaning of the bits in eieio_data_message_types values
#define EIEIO_PKT_HAS_PAYLOAD		0
#define EIEIO_PKT_32BIT			1

//! The EIEIO prefix types
typedef enum eieio_prefix_types {
    PREFIX_TYPE_LOWER_HALF_WORD,
    PREFIX_TYPE_UPPER_HALF_WORD
} eieio_prefix_types;

//! The parameter positions
typedef enum read_in_parameters {
    APPLY_PREFIX,
    PREFIX,
    PREFIX_TYPE,
    CHECK_KEYS,
    HAS_KEY,
    KEY_SPACE,
    MASK,
    BUFFER_REGION_SIZE,
    SPACE_BEFORE_DATA_REQUEST,
    RETURN_TAG_ID,
    RETURN_TAG_DEST,
    BUFFERED_IN_SDP_PORT
} read_in_parameters;

//! The memory regions
typedef enum memory_regions {
    SYSTEM,
    CONFIGURATION,
    RECORDING_REGION,
    BUFFER_REGION,
    PROVENANCE_REGION,
} memory_regions;

//! The provenance data items
typedef enum provenance_items {
    N_RECEIVED_PACKETS,
    N_SENT_PACKETS,
    INCORRECT_KEYS,
    INCORRECT_PACKETS,
    LATE_PACKETS
} provenance_items;

//! The number of regions that can be recorded
#define NUMBER_OF_REGIONS_TO_RECORD		1
#define SPIKE_HISTORY_CHANNEL			0

//! the minimum space required for a buffer to work
#define MIN_BUFFER_SPACE			10

//! the amount of ticks to wait between requests
#define TICKS_BETWEEN_REQUESTS			25

//! the maximum size of a packet
#define MAX_PACKET_SIZE				280

typedef struct __attribute__((packed)) {
    uint16_t event;
    uint16_t payload;
} event16_t;

typedef struct __attribute__((packed)) {
    uint16_t eieio_header_command;
    uint16_t chip_id;
    uint8_t processor;
    uint8_t pad1;
    uint8_t region;
    uint8_t sequence;
    uint32_t space_available;
} req_packet_sdp_t;

// Bits in the EIEIO message header
#define PKT_COUNT			 0	// 8 bits
#define PKT_TYPE			10	// 2 bits
#define HAS_TIMESTAMP			12	// 1 bit
#define PREFIX_APPLY			13	// 1 bit
#define PKT_MODE			14	// 1 bit
#define WANTS_PREFIX			15	// 1 bit

#endif //_EIEIO_STRUCTURES_H
