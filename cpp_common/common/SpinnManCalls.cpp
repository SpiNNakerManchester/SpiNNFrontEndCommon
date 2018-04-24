int SpinnManCalls::get_vcpu_address(int p)
{
    return CPU_INFO_OFFSET + (CPU_INFO_BYTES * p)
}


int SpinnManCalls::get_user_0_register_address_from_core(int p)
{
    int received_length;

    received_length = recv(this->sock, (char *) data, length, 0);

    if (received_length < 0) {
        throw strerror(errno);
    }
    return received_length;
}
