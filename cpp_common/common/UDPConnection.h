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

/// UDP socket that talks to a single remote UDP socket
class UDPConnection {
public:
    /// Create a connection specifying both ends of the connection
    UDPConnection(
            int local_port = 0,
            const char *local_host = nullptr,
            int remote_port = 0,
            const char *remote_host = nullptr);
    /// Create a connection specifying just the remote socket and allocating
    /// a local one automatically
    UDPConnection(
	    int remote_port,
            const std::string &remote_host)
	: UDPConnection(0, nullptr, remote_port, remote_host.c_str()) {}
    ~UDPConnection();

    // Modern C++ style API
    /// Receive a packet into the given buffer (must be large enough)
    bool receive_data(std::vector<uint8_t> &data) const;
    /// Receive a packet into the given buffer (must be large enough) and
    /// describe where it came from.
    bool receive_data_with_address(
	    std::vector<uint8_t> &data,
            struct sockaddr &address) const;
    /// Send an SDP message that has been prepared
    void send_message(const SDPMessage &message) const;
    /// Send some data that has been prepared
    void send_data(const std::vector<uint8_t> &data) const;
    /// Send some data that has been prepared to a specific remote socket
    void send_data_to(
	    const std::vector<uint8_t> &data, const sockaddr &address) const;

    // Old style API
    uint32_t receive_data(void *data, uint32_t length) const;
    uint32_t receive_data_with_address(
            void *data,
	    uint32_t length,
            sockaddr *address) const;
    void send_data(const void *data, uint32_t length) const;
    void send_data_to(
	    const void *data, uint32_t length, const sockaddr* address) const;

    // Simple accessors
    /// Get the actual port number used for the local socket
    uint32_t get_local_port() const;
    /// Get the actual IP address used for the local socket
    uint32_t get_local_ip() const;

private:
    /// The socket handle
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
