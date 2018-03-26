#include "UDPConnection.h"
#include <exception>
#include <unistd.h>
#include <string.h>
#include <stdio.h>
#include <time.h>
#include <errno.h>
#include <vector>

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

UDPConnection::UDPConnection(
        int local_port,
        char *local_host,
        int remote_port,
        char *remote_host)
{
    initSocketLibrary();
    sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock == 0) {
        throw "Socket could not be created";
    }

    local_ip_address = htonl(INADDR_ANY);
    if (local_host != NULL && local_host[0] != '\0') {
        hostent *lookup_address = gethostbyname(local_host);
        if (lookup_address == NULL) {
            throw "local_host address not found";
        }

        memcpy(&local_ip_address, lookup_address->h_addr,
                lookup_address->h_length);
    }

    sockaddr_in local_address;
    local_address.sin_family = AF_INET;
    local_address.sin_addr.s_addr = this->local_ip_address;
    local_address.sin_port = htons(local_port);

    bind(sock, (struct sockaddr *) &local_address, sizeof(local_address));

    can_send = false;
    remote_ip_address = 0;
    remote_port = 0;

    if (remote_host != NULL && remote_port != 0) {
        can_send = true;
        this->remote_port = remote_port;

        struct hostent *lookup_address = gethostbyname(remote_host);
        if (lookup_address == NULL) {

            throw "remote_host address not found";
        }

        memcpy(&this->remote_ip_address, lookup_address->h_addr,
                lookup_address->h_length);

        struct sockaddr_in remote_address;
        remote_address.sin_family = AF_INET;
        remote_address.sin_addr.s_addr = this->remote_ip_address;
        remote_address.sin_port = htons(remote_port);

        if (connect(sock, (struct sockaddr *) &remote_address,
                sizeof(remote_address)) < 0) {
            throw "Error connecting to remote address";
        }
    }

    socklen_t local_address_length = sizeof(local_address);
    if (getsockname(sock, (struct sockaddr *) &local_address,
            &local_address_length) < 0) {
        throw "Error getting local socket address";
    }
    this->local_ip_address = local_address.sin_addr.s_addr;
    this->local_port = ntohs(local_address.sin_port);
}

int UDPConnection::receive_data(char *data, int length)
{
    int received_length = recv(sock, (char *) data, length, 0);

    if (received_length < 0) {
        throw strerror(errno);
    }
    return received_length;
}

int UDPConnection::receive_data(std::vector<uint8_t> &data)
{
    int received_length = recv(sock, (char *) data.data(), data.size(), 0);

    if (received_length < 0) {
        throw strerror(errno);
    }
    data.resize(received_length);
    return received_length;
}

int UDPConnection::receive_data_with_address(
        char *data,
        int length,
        struct sockaddr *address)
{
    int address_length = sizeof(*address);

    int received_length = recvfrom(sock, (char *) data, length, 0, address,
            (socklen_t *) &address_length);
    if (received_length < 0) {
        throw strerror(errno);
    }
    return received_length;
}

int UDPConnection::receive_data_with_address(
	std::vector<uint8_t> &data,
        struct sockaddr &address)
{
    int address_length = sizeof(address);
    int received_length = recvfrom(sock, (char *) data.data(), data.size(),
	    0, &address, (socklen_t *) &address_length);
    if (received_length < 0) {
        throw strerror(errno);
    }
    return received_length;
}

void UDPConnection::send_data(const char *data, int length)
{
    int a = send(sock, (const char *) data, length, 0);

    if (a < 0) {
        throw "Error sending data";
    }
}

void UDPConnection::send_data(const std::vector<uint8_t> &data)
{
    int a = send(sock, (const char *) data.data(), data.size(), 0);

    if (a < 0) {
        throw "Error sending data";
    }
}

void UDPConnection::send_message(SDPMessage &message)
{
    std::vector<uint8_t> buffer;
    message.convert_to_byte_vector(buffer);
    send_data(buffer);
}

void UDPConnection::send_data_to(
	const char *data, int length, const sockaddr *address)
{
    if (sendto(sock, (const char *) data, length, 0,
            (const struct sockaddr *) address, sizeof(*address)) < 0) {
        throw "Error sending data";
    }
}

void UDPConnection::send_data_to(
	const std::vector<uint8_t> &data, const sockaddr &address)
{
    if (sendto(sock, (const char *) data.data(), data.size(), 0,
            (const struct sockaddr *) &address, sizeof(address)) < 0) {
        throw "Error sending data";
    }
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
    shutdown(sock, SHUT_RDWR);
    close(sock);
}
