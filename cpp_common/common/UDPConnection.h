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
#include <memory>
#include "SDPMessage.h"

/// Base implementation for a UDP socket that talks to a single remote
/// UDP socket.
class UDPConnectionBase {
public:
    /// Create a connection specifying both ends of the connection
    UDPConnectionBase(
            int local_port = 0,
            const char *local_host = nullptr,
            int remote_port = 0,
            const char *remote_host = nullptr);
    ~UDPConnectionBase();

    // Old style API
    uint32_t receive_bytes(void *data, uint32_t length) const;
    uint32_t receive_bytes_with_address(
            void *data,
	    uint32_t length,
            sockaddr *address) const;
    void send_bytes(const void *data, uint32_t length) const;
    void send_bytes_to(
	    const void *data, uint32_t length, const sockaddr* address) const;

    // Simple accessors
    /// Get the actual port number used for the local socket
    uint32_t get_local_port() const
    {
	return (uint32_t) local_port;
    }
    /// Get the actual IP address used for the local socket
    uint32_t get_local_ip() const
    {
	return (uint32_t) local_ip_address;
    }

private:
    /// The socket handle
    int sock;
    bool can_send;
    int local_port;
    unsigned int local_ip_address;
    int remote_port;
    unsigned int remote_ip_address;
};

/// UDP socket that talks to a single remote UDP socket.
template<class Allocator=std::allocator<uint8_t>>
class UDPConnection : public UDPConnectionBase {
    typedef std::vector<typename Allocator::value_type, Allocator> buffer_t;
public:
    /// Create a connection specifying just the remote socket and allocating
    /// a local one automatically
    UDPConnection(
	    int remote_port,
            const std::string &remote_host)
	: UDPConnectionBase(0, nullptr, remote_port, remote_host.c_str()) {}

    // Modern C++ style API
    /// Receive a packet into the given buffer (must be large enough)
    bool receive_data(buffer_t &data) const
    {
        uint32_t received_length = receive_bytes(data.data(), data.size());
        data.resize(received_length);
        return received_length > 0;
    }

    /// Receive a packet into the given buffer (must be large enough) and
    /// describe where it came from.
    bool receive_data_with_address(
	    buffer_t &data,
	    struct sockaddr &address) const
    {
        uint32_t received_length = receive_bytes_with_address(data.data(),
    	    data.size(), &address);
        data.resize(received_length);
        return received_length > 0;
    }
    /// Send an SDP message that has been prepared
    void send_message(const SDPMessage &message) const
    {
	std::vector<uint8_t> buffer;
        message.convert_to_byte_vector(buffer);
        send_data(buffer);
    }

    /// Send some data that has been prepared
    template<class AnyAllocator>
    void send_data(const std::vector<uint8_t, AnyAllocator> &data) const
    {
        send_bytes(data.data(), data.size());
    }

    /// Send some data that has been prepared to a specific remote socket
    template<class AnyAllocator>
    void send_data_to(
    	const std::vector<uint8_t, AnyAllocator> &data, const sockaddr &address) const
    {
        send_bytes_to(data.data(), data.size(), &address);
    }
};

struct TimeoutException: public std::exception {
};

#endif // _UDP_CONNECTION_H_
