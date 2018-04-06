#include "UDPConnection.h"
#include <exception>
#include <unistd.h>
#include <string.h>
#include <stdio.h>
#include <time.h>
#include <errno.h>
#include <vector>
#include <chrono>

using namespace std;
using namespace std::literals::chrono_literals; // BLACK MAGIC!

static constexpr auto TIMEOUT_PER_RECEIVE = 1000ms;

// Simple helpers for determining if there is an error
template<typename Int>
static bool error(Int value) {
    return value < 0;
}

template<typename T>
static bool error(T *value) {
    return value == nullptr;
}

template<typename T>
static bool error(const T *value) {
    return value == nullptr;
}

// Extra magic for Windows.
static void initSocketLibrary(void) {
    static bool initialised = false;
    if (initialised) {
	return;
    }

#ifdef WIN32
    WSADATA wsaData; // if this doesn't work
    //WSAData wsaData; // then try this instead
#include <UDPConnection.h>
    if (WSAStartup(MAKEWORD(1, 1), &wsaData) != 0) {
        fprintf(stderr, "WSAStartup failed.\n");
        exit(1);
    }
#endif // WIN32
    initialised = true;
}

template<class TimeRep, class TimePeriod>
static void setSocketTimeout(
	int sock, chrono::duration<TimeRep, TimePeriod> d)
{
#ifdef WIN32
    auto ms = chrono::duration_cast<chrono::milliseconds>(d);
    DWORD timeout = (DWORD) ms.count();
#else
    auto sec = chrono::duration_cast<chrono::seconds>(d);
    struct timeval timeout;
    timeout.tv_sec = sec.count();
    timeout.tv_usec = chrono::duration_cast<chrono::microseconds>(
	    d - sec).count();
#endif
    if (error(
	    setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &timeout,
		    sizeof(timeout)))) {
	throw "Socket timeout could not be set";
    }
}

static inline struct sockaddr get_address(const char *ip_address, int port)
{
    const hostent *lookup_address = gethostbyname(ip_address);
    if (error(lookup_address)) {
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

UDPConnection::UDPConnection(
        int local_port,
        const char *local_host,
        int remote_port,
        const char *remote_host)
    : local_ip_address(htonl(INADDR_ANY))
{
    initSocketLibrary();
    sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (error(sock)) {
        throw "Socket could not be created";
    }
    const int buffer_size = 1024 * 1024;
    if (error(
	    setsockopt(sock, SOL_SOCKET, SO_RCVBUF, &buffer_size,
		    sizeof(buffer_size)))) {
        throw "Socket buffer size could not be set";
    }

    sockaddr local_address;
    if (local_host != nullptr && local_host[0] != '\0') {
	local_address = get_address(local_host, local_port);
    } else {
	sockaddr_in *local = (sockaddr_in *) &local_address;
	local->sin_family = AF_INET;
	local->sin_addr.s_addr = htonl(INADDR_ANY);
	local->sin_port = htons(local_port);
    }

    setSocketTimeout(sock, TIMEOUT_PER_RECEIVE);
    if (error(::bind(sock, &local_address, sizeof(local_address)))) {
	throw "Socket could not be bound to local address";
    }

    can_send = false;
    remote_ip_address = 0;
    this->remote_port = 0;

    if (remote_host != nullptr && remote_port != 0) {
        can_send = true;
        this->remote_port = remote_port;
        sockaddr remote_address = get_address(remote_host, remote_port);
        if (error(connect(sock, &remote_address, sizeof(remote_address)))) {
            throw "Error connecting to remote address";
        }
    }

    sockaddr_in local_inet_addr;
    socklen_t local_address_length = sizeof(local_inet_addr);
    if (error(getsockname(sock, (struct sockaddr *) &local_inet_addr,
            &local_address_length))) {
        throw "Error getting local socket address";
    }
    local_ip_address = local_inet_addr.sin_addr.s_addr;
    this->local_port = ntohs(local_inet_addr.sin_port);
}

uint32_t UDPConnection::receive_data(void *data, int length)
{
    int received_length = recv(sock, data, length, 0);

    if (error(received_length)) {
	if (errno == EWOULDBLOCK || errno == EAGAIN) {
	    received_length = 0;
	} else {
	    throw strerror(errno);
	}
    }
    return uint32_t(received_length);
}

bool UDPConnection::receive_data(vector<uint8_t> &data)
{
    uint32_t received_length = receive_data(data.data(), data.size());
    data.resize(received_length);
    return received_length > 0;
}

uint32_t UDPConnection::receive_data_with_address(
	void *data,
	int length,
	struct sockaddr *address)
{
    int address_length = sizeof(*address);
    int received_length = recvfrom(sock, data, length, 0, address,
	    (socklen_t *) &address_length);
    if (error(received_length)) {
	if (errno == EWOULDBLOCK || errno == EAGAIN) {
	    received_length = 0;
	} else {
	    throw strerror(errno);
	}
    }
    return uint32_t(received_length);
}

bool UDPConnection::receive_data_with_address(
	vector<uint8_t> &data,
	struct sockaddr &address)
{
    uint32_t received_length = receive_data_with_address(data.data(),
	    data.size(), &address);
    data.resize(received_length);
    return received_length > 0;
}

void UDPConnection::send_data(const void *data, int length)
{
    if (error(send(sock, data, length, 0))) {
        throw "Error sending data";
    }
}

void UDPConnection::send_data(const vector<uint8_t> &data)
{
    send_data(data.data(), data.size());
}

void UDPConnection::send_message(SDPMessage &message)
{
    vector<uint8_t> buffer;
    message.convert_to_byte_vector(buffer);
    send_data(buffer);
}

void UDPConnection::send_data_to(
	const void *data, int length, const sockaddr *address)
{
    if (error(sendto(sock, data, length, 0,
            (const struct sockaddr *) address, sizeof(*address)))) {
        throw "Error sending data";
    }
}

void UDPConnection::send_data_to(
	const vector<uint8_t> &data, const sockaddr &address)
{
    send_data_to(data.data(), data.size(), &address);
}

uint32_t UDPConnection::get_local_port()
{
    return (uint32_t) local_port;
}

uint32_t UDPConnection::get_local_ip()
{
    return (uint32_t) local_ip_address;
}

UDPConnection::~UDPConnection()
{
    shutdown(sock, SHUT_RDWR);	// Ignore errors
    close(sock);		// Ignore errors
}
