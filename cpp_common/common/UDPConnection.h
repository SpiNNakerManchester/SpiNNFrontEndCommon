#ifndef _UDP_CONNECTION_H_
#define _UDP_CONNECTION_H_

#ifndef WIN32
#include <netdb.h>
#include <arpa/inet.h>
#else
#include <windows.h>
#include <ws2tcpip.h>
#define close(sock)

#define SHUT_RD   SD_RECEIVE
#define SHUT_WR   SD_SEND
#define SHUT_RDWR SD_BOTH

typedef unsigned int uint;
typedef unsigned short ushort;
#endif

#include <cstdint>
#include <vector>
#include <string>
#include "SDPMessage.h"

class UDPConnection {
public:
    UDPConnection(
            int local_port = 0,
            const char *local_host = nullptr,
            int remote_port = 0,
            const char *remote_host = nullptr);
    UDPConnection(
	    int remote_port,
            std::string &remote_host)
	: UDPConnection(0, nullptr, remote_port, remote_host.c_str()) {}
    ~UDPConnection();

    // Modern C++ style API
    bool receive_data(std::vector<uint8_t> &data);
    bool receive_data_with_address(
	    std::vector<uint8_t> &data,
            struct sockaddr &address);
    void send_message(SDPMessage &message);
    void send_data(const std::vector<uint8_t> &data);
    void send_data_to(
	    const std::vector<uint8_t> &data, const sockaddr &address);

    // Old style API
    uint32_t receive_data(void *data, int length);
    uint32_t receive_data_with_address(
            void *data,
            int length,
            sockaddr *address);
    void send_data(const void *data, int length);
    void send_data_to(
	    const void *data, int length, const sockaddr* address);

    // Simple accessors
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

struct TimeoutException: public std::exception {
};

#endif // _UDP_CONNECTION_H_
