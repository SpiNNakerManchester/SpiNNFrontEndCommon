#ifndef _UDP_CONNECTION_H_
#define _UDP_CONNECTION_H_

#ifndef WIN32
#include <netdb.h>
#include <arpa/inet.h>
#else
#include <windows.h>
#include <ws2tcpip.h>
#define bzero(b, len)     (memset((b), '\0', (len)), (void) 0)
#define bcopy(b1, b2, len) (memmove((b2), (b1), (len)), (void) 0)
#define close(sock)

#define SHUT_RD   SD_RECEIVE
#define SHUT_WR   SD_SEND
#define SHUT_RDWR SD_BOTH

typedef unsigned int uint;
typedef unsigned short ushort;
#endif

#include <stdlib.h>
#include <string.h>
#include <iostream>
#include <cstdint>
#include <vector>
#include <string>
#include "SDPMessage.h"

using namespace std;

static inline struct sockaddr get_address(const char *ip_address, int port)
{
    hostent *lookup_address = gethostbyname(ip_address);
    if (lookup_address == NULL) {
        throw "host address not found";
    }
    union {
	sockaddr sa;
	sockaddr_in in;
    } local_address;
    local_address.in.sin_family = AF_INET;
    memcpy(&local_address.in.sin_addr.s_addr, lookup_address->h_addr,
            lookup_address->h_length);
    local_address.in.sin_port = htons(port);

    return local_address.sa;
}

class UDPConnection {
public:
    UDPConnection(
            int local_port = 0,
            const char *local_host = NULL,
            int remote_port = 0,
            const char *remote_host = NULL);
    UDPConnection(
	    int remote_port,
            string &remote_host)
	: UDPConnection(0, NULL, remote_port, remote_host.c_str()) {}

    ~UDPConnection();
    int receive_data(char *data, int length);
    bool receive_data(vector<uint8_t> &data);
    int receive_data_with_address(
            char *data,
            int length,
            struct sockaddr *address);
    bool receive_data_with_address(
	    vector<uint8_t> &data,
            struct sockaddr &address);
    void send_data(const char *data, int length);
    void send_data(const vector<uint8_t> &data);
    void send_message(SDPMessage &message);
    void send_data_to(
	    const char *data, int length, const struct sockaddr* address);
    void send_data_to(
	    const vector<uint8_t> &data, const struct sockaddr &address);
    uint32_t get_local_port();
    uint32_t get_local_ip();

private:
    int sock;
    bool can_send;
    int local_port;
    unsigned int local_ip_address;
    int remote_port;
    unsigned int remote_ip_address;
};

struct TimeoutException: public exception {
};

#endif // _UDP_CONNECTION_H_
