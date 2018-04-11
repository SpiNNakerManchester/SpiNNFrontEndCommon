INSTALL_LOCATION=../../spinn_front_end_common/common_host_binaries
COMMON=../common

SRCS=host_data_receiver.cpp main.cpp
HEADERS=$(COMMON)/SDPHeader.h $(COMMON)/SDPMessage.h\
        $(COMMON)/UDPConnection.h PQueue.h Messages.h host_data_receiver.h
TARGET=host_data_receiver
LIBS=-lpthread -L$(COMMON) -lcommon
INSTALL ?= install
OPT=-O3

all: install

build: $(TARGET)
$(TARGET): $(SRCS) $(HEADERS) $(COMMON)/libcommon.a
	$(CXX) $(CXXFLAGS) $(OPT) -I$(COMMON) -o $@ $(SRCS) -std=c++14 $(LIBS)

install: $(TARGET)
	$(INSTALL) -c $(TARGET) $(INSTALL_LOCATION)

clean:
	$(RM) $(TARGET)
install-clean:
	$(RM) $(INSTALL_LOCATION)/$(TARGET)

.PHONY: all build install clean
