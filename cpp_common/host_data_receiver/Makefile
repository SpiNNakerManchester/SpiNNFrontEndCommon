INSTALL_LOCATION=../../../../spinn_front_end_common/utility_models

SRCS=SDPHeader.cpp SDPMessage.cpp UDPConnection.cpp host_data_receiver.cpp main.cpp
HEADERS=PQueue.h SDPHeader.h SDPMessage.h UDPConnection.h host_data_receiver.h
TARGET=host_data_receiver
LIBS=-lpthread
INSTALL ?= install

all: install

build: $(TARGET)
$(TARGET): $(SRCS) $(HEADERS)
	$(CXX) -o $@ $(SRCS) -std=c++14 $(LIBS)

install: $(TARGET)
	$(INSTALL) -c $(TARGET) $(INSTALL_LOCATION)

clean:
	$(RM) $(TARGET)
install-clean:
	$(RM) $(INSTALL_LOCATION)/$(TARGET)

.PHONY: all build install clean
