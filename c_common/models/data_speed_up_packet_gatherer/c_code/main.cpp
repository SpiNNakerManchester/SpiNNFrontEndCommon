#include "host_data_receiver.h"

int main(int argc, char *argv[])  {

    // constants for arguments
    static const int N_ARGS = 13;
    static const int IP_ADDRESS_SIZE = 24;
    static const int FILE_PATH_SIZE = 1024;

    // enum for arg positions
    enum arg_placements{
        PLACEMENT_X_POSITION = 3,
        PLACEMENT_Y_POSITION = 4,
        PLACEMENT_P_POSITION = 5,
        PORT_NUMBER_POSITION = 2,
        HOSTNAME_POSITION = 1,
        FILE_PATH_READ_POSITION = 6,
		FILE_PATH_MISS_POSITION = 7,
		LENGTH_IN_BYTES = 8,
		MEMORY_ADDRESS = 9,
		CHIP_X = 10,
		CHIP_Y = 11,
		IPTAG = 12};

    // variables
    int i;
    int placement_x = 0;
    int placement_y = 0;
    int placement_p = 0;
    int port_connection = 0;
    int length_in_bytes = 0;
    int memory_address = 0;
    char *hostname = NULL;
    char *file_pathr = NULL;
    char *file_pathm = NULL;
    //FILE * stored_data;
    char * output = NULL;
    char *buffer;
    int chip_x = 0;
    int chip_y = 0;
    int iptag = 0;



    // placement x, placement y, placement p, port, host, data loc
    if(argc != N_ARGS) {
        printf("not the correct number of parameters");
        return 1;
    }

    // get arguments
    placement_x = atoi(argv[PLACEMENT_X_POSITION]);
    placement_y = atoi(argv[PLACEMENT_Y_POSITION]);
    placement_p = atoi(argv[PLACEMENT_P_POSITION]);
    port_connection = atoi(argv[PORT_NUMBER_POSITION]);
    length_in_bytes = atoi(argv[LENGTH_IN_BYTES]);
    memory_address = atoi(argv[MEMORY_ADDRESS]);
    hostname = argv[HOSTNAME_POSITION];
    file_pathr = argv[FILE_PATH_READ_POSITION];
    file_pathm = argv[FILE_PATH_MISS_POSITION];
    chip_x = atoi(argv[CHIP_X]);
    chip_y = atoi(argv[CHIP_Y]);
    iptag = atoi(argv[IPTAG]);

    host_data_receiver collector(port_connection, placement_x, placement_y, placement_p, hostname,
                    length_in_bytes, memory_address, chip_x, chip_y, iptag);

    collector.get_data_threadable(file_pathr, file_pathm);

    return 0;
}