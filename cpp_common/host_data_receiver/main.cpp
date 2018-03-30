#include "host_data_receiver.h"
#include <string>

class Arguments {
private:
    int argc;
    char **argv;
public:
    Arguments(int argc, char **argv) : argc(argc), argv(argv) {}
    const char *operator[](int index) {
	if (index < 0 || index >= argc) {
	    throw std::invalid_argument("no such argument");
	}
	return argv[index];
    }
    int length() {
	return argc;
    }
};

static inline void parse_arg(Arguments &args, int index, int &variable)
{
    try {
	std::string s(args[index]);
	variable = std::stoi(s);
    } catch (std::invalid_argument &e) {
	cout << "couldn't parse integer argument " << index << " '" <<
		args[index] << "'" << endl;
	exit(1);
    }
}

int main(int argc, char *argv[])
{
    // Wrap argv with a safe accessor
    Arguments args(argc, argv);

    // constants for arguments
    static const int N_ARGS = 13;

    // enum for arg positions
    enum arg_placements {
        HOSTNAME_POSITION = 1,
        PORT_NUMBER_POSITION = 2,
        PLACEMENT_X_POSITION = 3,
        PLACEMENT_Y_POSITION = 4,
        PLACEMENT_P_POSITION = 5,
        FILE_PATH_READ_POSITION = 6,
        FILE_PATH_MISS_POSITION = 7,
        LENGTH_IN_BYTES = 8,
        MEMORY_ADDRESS = 9,
        CHIP_X = 10,
        CHIP_Y = 11,
        IPTAG = 12
    };

    // placement x, placement y, placement p, port, host, data loc
    if (args.length() != N_ARGS) {
        cout << "usage: " << args[0] << " <hostname> <port> <placement.x> "
        	"<placement.y> <placement.p> <read.file> <miss.file> "
        	"<length> <address> <chip.x> <chip.y> <iptag>" << endl;
        return 1;
    }

    // variables
    int placement_x = 0;
    int placement_y = 0;
    int placement_p = 0;
    int port_connection = 0;
    int length_in_bytes = 0;
    int memory_address = 0;
    int chip_x = 0;
    int chip_y = 0;
    int iptag = 0;

    // get arguments
    parse_arg(args, PLACEMENT_X_POSITION, placement_x);
    parse_arg(args, PLACEMENT_Y_POSITION, placement_y);
    parse_arg(args, PLACEMENT_P_POSITION, placement_p);
    parse_arg(args, PORT_NUMBER_POSITION, port_connection);
    parse_arg(args, LENGTH_IN_BYTES, length_in_bytes);
    parse_arg(args, MEMORY_ADDRESS, memory_address);
    const char *hostname = args[HOSTNAME_POSITION];
    const char *file_pathr = args[FILE_PATH_READ_POSITION];
    const char *file_pathm = args[FILE_PATH_MISS_POSITION];
    parse_arg(args, CHIP_X, chip_x);
    parse_arg(args, CHIP_Y, chip_y);
    parse_arg(args, IPTAG, iptag);

    host_data_receiver collector(port_connection, placement_x, placement_y,
            placement_p, hostname, length_in_bytes, memory_address, chip_x,
            chip_y, iptag);

    collector.get_data_threadable(file_pathr, file_pathm);

    return 0;
}
