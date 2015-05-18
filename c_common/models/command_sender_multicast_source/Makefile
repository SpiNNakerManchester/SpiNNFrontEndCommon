APP = command_sender_multicast_source
BUILD_DIR = build/
OBJECTS = command_sender_multicast_source.o

# Run md5sum on application name and extract first 8 bytes
APPLICATION_NAME_HASH = $(shell echo -n "$(APP)" | md5sum | cut -c 1-8)

CFLAGS += -DAPPLICATION_NAME_HASH=0x$(APPLICATION_NAME_HASH)

include ../Makefile.common
