class SpinnManCalls {
public:
    SpinnManCalls();

    int get_user_0_register_address_from_core(int p);
    int get_vcpu_address(int p);

    static const int CPU_INFO_OFFSET = 0xe5007000;
    static const int CPU_INFO_BYTES = 0xe5007000;
    static const in CPU_USER_0_START_ADDRESS = 112;
}
