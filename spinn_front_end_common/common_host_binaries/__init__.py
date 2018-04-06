import subprocess
import os

DATA_OUT_OUT_FILE = "./fileout.txt"
DATA_OUT_MISSING_SEQ_NUMS_FILE = "./missing.txt"
DATA_OUT_BINARY_NAME = "/host_data_receiver"


def run_host_data_receiver(
        remote_ip_address, port_value, placement_x, placement_y, placement_p,
        length_in_bytes, memory_address, tag, connection_chip_x,
        connection_chip_y):
    """ runs the host receiver c code as a sub process

    :param remote_ip_address: the remote ip address for the spinnaker machine
    :param port_value: the port value for data out packets
    :param placement_x: the x coordinate for where data is going to
    :param placement_y: the y coordinate for where data is going to
    :param placement_p: the p coordinate for where data is going to
    :param length_in_bytes: the number of bytes to extract
    :param memory_address: the memory address to start reading from
    :param tag: the iptag to utilise
    :param connection_chip_x: the chip x of the connection we're going to use
    :param connection_chip_y: the chip y of the connection we're going to use
    :return: a string of the data
    :rtype string


    """
    # =======================================================================
    # receiver = host_data_receiver()
    # buf = receiver.get_data_for_python(
    #    str(connection.remote_ip_address),
    #    int(constants.SDP_PORTS.EXTRA_MONITOR_CORE_DATA_SPEED_UP.value),
    #    int(placement.x),
    #    int(placement.y),
    #    int(placement.p),
    #    int(length_in_bytes),
    #    int(memory_address),
    #    int(chip_x),
    #    int(chip_y),
    #    int(self._tag))
    # =======================================================================

    path_list = os.path.realpath(__file__).split("/")

    subprocess.call([
        #"java",
        #"-jar",
        #"/".join(path_list[0:len(path_list) - 1]) + "/" +"java_common_2.jar",
        "/" + "/".join(path_list[0:len(path_list) - 1]) + DATA_OUT_BINARY_NAME,
        str(remote_ip_address),
        str(port_value),
        str(placement_x),
        str(placement_y),
        str(placement_p),
        str(DATA_OUT_OUT_FILE),
        str(DATA_OUT_MISSING_SEQ_NUMS_FILE),
        str(length_in_bytes),
        str(memory_address),
        str(connection_chip_x),
        str(connection_chip_y),
        str(tag)])

    # read in all data
    with open(DATA_OUT_OUT_FILE, "r") as fp:
        buf = fp.read()

    return buf
