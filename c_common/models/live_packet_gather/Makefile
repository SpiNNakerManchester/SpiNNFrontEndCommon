APP = live_packet_gather
BUILD_DIR = build/
OBJECTS = live_packet_gather.o

# Run md5sum on application name and extract first 8 bytes
APPLICATION_NAME_HASH = $(shell echo -n "$(APP)" | md5sum | cut -c 1-8)

CFLAGS += -DAPPLICATION_NAME_HASH=0x$(APPLICATION_NAME_HASH)

include ../Makefile.common
