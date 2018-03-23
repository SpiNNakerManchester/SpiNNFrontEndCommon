#include "UDPConnection.h"
#include <exception>
#include <unistd.h>
#include <string.h>
#include <stdio.h>
#include <time.h>
#include <errno.h>


UDPConnection::UDPConnection(
        int local_port, char *local_host, int remote_port, char *remote_host) {

#ifdef WIN32
    WSADATA wsaData; // if this doesn't work
    //WSAData wsaData; // then try this instead

    if (WSAStartup(MAKEWORD(1, 1), &wsaData) != 0) {
        fprintf(stderr, "WSAStartup failed.\n");
        exit(1);
    }
#endif

    this->sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (this->sock == 0) {
        throw "Socket could not be created";
    }

    this->local_ip_address = htonl(INADDR_ANY);
    if (local_host != NULL) {
        struct hostent *lookup_address = gethostbyname(local_host);
        if (lookup_address == NULL) {
            throw "local_host address not found";
        }

        memcpy(&this->local_ip_address, lookup_address->h_addr,
               lookup_address->h_length);
    }


    struct sockaddr_in local_address;
    local_address.sin_family = AF_INET;
    local_address.sin_addr.s_addr = this->local_ip_address;
    local_address.sin_port = htons(local_port);

    bind(this->sock, (struct sockaddr *) &local_address,
             sizeof(local_address));

    this->can_send = false;
    this->remote_ip_address = 0;
    this->remote_port = 0;

    if (remote_host != NULL && remote_port != 0) {
        this->can_send = true;
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

        if (connect(this->sock, (struct sockaddr *) &remote_address,
                    sizeof(remote_address)) < 0) {
            throw "Error connecting to remote address";
        }
    }

    socklen_t local_address_length = sizeof(local_address);
    if (getsockname(this->sock, (struct sockaddr *) &local_address,
                    &local_address_length) < 0) {
        throw "Error getting local socket address";
    }

    this->local_ip_address = local_address.sin_addr.s_addr;
    this->local_port = ntohs(local_address.sin_port);
}

int UDPConnection::receive_data(char *data, int length) {

	int received_length;

    received_length = recv(this->sock, (char *) data, length, 0);

    if (received_length < 0) {

        throw strerror(errno);

    }
    return received_length;
}

int UDPConnection::receive_data_with_address(char *data, int length,
                                             struct sockaddr *address) {

	int received_length;

    int address_length = sizeof(*address);

    received_length = recvfrom(this->sock, (char *) data, length, 0,
                                   address, (socklen_t *) &address_length);
    if (received_length < 0) {

        throw strerror(errno);
    }
    return received_length;
}

void UDPConnection::send_data(char *data, int length) {

	int a = send(this->sock, (const char *) data, length, 0);
	 
    if (a < 0) {

        throw "Error sending data";
    }
}

void UDPConnection::send_data_to(char *data, int length,
                                 sockaddr* address) {

    if (sendto(this->sock, (const char *) data, length, 0,
               (const struct sockaddr *) address, sizeof(*address)) < 0) {
        throw "Error sending data";
    }
}

uint32_t UDPConnection::get_local_port() {

    return (uint32_t)this->local_port;
}

uint32_t UDPConnection::get_local_ip() {

    return (uint32_t)this->local_ip_address;
}

UDPConnection::~UDPConnection() {

    shutdown(this->sock, SHUT_RDWR);
    close(this->sock);
}

