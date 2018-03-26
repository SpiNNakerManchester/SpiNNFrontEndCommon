INSTALL_LOCATION=../../spinn_front_end_common/common_host_binaries

SRCS=../common/SDPHeader.cpp ../common/SDPMessage.cpp\
     ../common/UDPConnection.cpp host_data_receiver.cpp main.cpp
HEADERS=PQueue.h ../common/SDPHeader.h ../common/SDPMessage.h\
        ../common/UDPConnection.h host_data_receiver.h
TARGET=host_data_receiver
LIBS=-lpthread
INSTALL ?= install

all: install

build: $(TARGET)
$(TARGET): $(SRCS) $(HEADERS)
	$(CXX) $(CXXFLAGS) -o $@ $(SRCS) -std=c++14 $(LIBS)

install: $(TARGET)
	$(INSTALL) -c $(TARGET) $(INSTALL_LOCATION)

clean:
	$(RM) $(TARGET)
install-clean:
	$(RM) $(INSTALL_LOCATION)/$(TARGET)

.PHONY: all build install clean
