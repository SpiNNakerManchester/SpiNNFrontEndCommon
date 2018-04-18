#include "host_data_receiver.h"
#include <string>
#include <iostream>
#include <cstdio>
#include <ctime>
#include "timing.h"

/// Wrapper round the arguments to the program
class Arguments {
private:
    int argc;
    char **argv;
public:
    /// Make the wrapper
    Arguments(int argc, char **argv) :
	    argc(argc), argv(argv)
    {
    }

    /// Retrieve an argument
    const std::string operator[](
	    int index) ///< [in] the index of the argument to read
    {
	if (index < 0 || index >= argc) {
	    throw std::invalid_argument("no such argument");
	}
	return argv[index];
    }

    /// Get how many arguments there were
    int length()
    {
	return argc;
    }
};

/// Parse an integer argument
static inline int parse_arg(Arguments &args, int index)
{
    try {
	return std::stoi(args[index]);
    } catch (std::invalid_argument &e) {
	std::cout << "couldn't parse integer argument " << index << " '"
		<< args[index] << "'" << std::endl;
	exit(1);
    }
}

/// Total number of arguments
static constexpr int N_ARGS = 13;

/// enum for arg positions
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

/// The real main function
static void main_body(Arguments &args)
{
    double start = get_wall_time();

    // Sanity check the number of arguments
    if (args.length() != N_ARGS) {
	std::cerr << "usage: " << args[0]
		<< " <hostname> <port> <placement.x> <placement.y> "
			"<placement.p> <data.file> <miss.file> "
			"<length> <address> <chip.x> <chip.y> <iptag>"
		<< std::endl;
	exit(1);
    }

    // parse arguments
    int placement_x = parse_arg(args, PLACEMENT_X_POSITION);
    int placement_y = parse_arg(args, PLACEMENT_Y_POSITION);
    int placement_p = parse_arg(args, PLACEMENT_P_POSITION);
    int port_connection = parse_arg(args, PORT_NUMBER_POSITION);
    int length_in_bytes = parse_arg(args, LENGTH_IN_BYTES);
    int memory_address = parse_arg(args, MEMORY_ADDRESS);
    std::string hostname = args[HOSTNAME_POSITION];
    std::string file_pathr = args[FILE_PATH_READ_POSITION];
    std::string file_pathm = args[FILE_PATH_MISS_POSITION];
    int chip_x = parse_arg(args, CHIP_X);
    int chip_y = parse_arg(args, CHIP_Y);
    int iptag = parse_arg(args, IPTAG);

    // Make the data transfer class
    host_data_receiver collector(port_connection, placement_x, placement_y,
	    placement_p, hostname, length_in_bytes, memory_address, chip_x,
	    chip_y, iptag);

    // Tell it to move the data to the specified files
    collector.get_data_threadable(file_pathr, file_pathm);

    double duration = get_wall_time() - start;

    std::cout << "time taken to extract " << (length_in_bytes / 1024. / 1024.)
	    << " MB with just C++ is " << duration << " (MB/s of "
	    << ((length_in_bytes / 1024. / 1024.) / duration) << ")"
	    << std::endl;
}

/// Wrapper that ensures that exceptions don't leak
int main(int argc, char *argv[])
{
    // Wrap argv with a safe accessor
    Arguments args(argc, argv);
    try {
	main_body(args);
	return 0;
    } catch (...) {
	// Any exception hits here, blow up
	std::cerr << "unexpected exception" << std::endl;
	return 1;
    }
}
