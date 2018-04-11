all: libcommon.a

CXXFLAGS += -std=c++14 -O3

OBJS = SDPHeader.o SDPMessage.o UDPConnection.o

libcommon.a: $(OBJS)
	$(AR) rcs $@ $^
SDPHeader.o: SDPHeader.cpp SDPHeader.h
SDPMessage.o: SDPMessage.cpp SDPMessage.h SDPHeader.h
UDPConnection.o: UDPConnection.cpp UDPConnection.h SDPMessage.h SDPHeader.h

clean:
	-$(RM) libcommon.a $(OBJS)

.PHONY: all clean
