# spinnman imports
from spinnman.connections.socket_address_with_chip import SocketAddressWithChip
from spinnman.transceiver import create_transceiver_from_hostname
from spinnman.model.bmp_connection_data import BMPConnectionData

# front end common imports
from spinn_front_end_common.utilities import exceptions

# general imports
import re


class FrontEndCommonMachineGenerator(object):
    """ Interface to make a transceiver and a spinn_machine object
    """

    __slots__ = []

    def __call__(
            self, hostname, bmp_details, downed_chips, downed_cores,
            downed_links, board_version, auto_detect_bmp, enable_reinjection,
            scamp_connection_data, boot_port_num, reset_machine_on_start_up,
            max_sdram_size=None, max_core_id=None):
        """
        :param hostname: the hostname or ip address of the spinnaker machine
        :param bmp_details: the details of the BMP connections
        :param downed_chips: the chips that are down which SARK thinks are\
                alive
        :param downed_cores: the cores that are down which SARK thinks are\
                alive
        :param board_version: the version of the boards being used within the\
                machine (1, 2, 3, 4 or 5)
        :param auto_detect_bmp: boolean which determines if the BMP should
               be automatically determined
        :param enable_reinjection: True if dropped packet reinjection is to be\
               enabled
        :param boot_port_num: the port num used for the boot connection
        :param scamp_connection_data: the list of scamp connection data or\
               None
        :param max_sdram_size: the maximum SDRAM each chip can say it has
               (mainly used in debugging purposes)
        :type max_sdram_size: int or None
        """

        # if the end user gives you scamp data, use it and don't discover them
        if scamp_connection_data is not None:
            scamp_connection_data = \
                self._sort_out_scamp_connections(scamp_connection_data)

        # sort out BMP connections into list of strings
        bmp_connection_data = self._sort_out_bmp_string(bmp_details)

        txrx = create_transceiver_from_hostname(
            hostname=hostname, bmp_connection_data=bmp_connection_data,
            version=board_version, ignore_chips=downed_chips,
            ignore_cores=downed_cores, ignored_links=downed_links,
            auto_detect_bmp=auto_detect_bmp,
            boot_port_no=boot_port_num,
            scamp_connections=scamp_connection_data,
            max_sdram_size=max_sdram_size, max_core_id=max_core_id)

        if reset_machine_on_start_up:
            txrx.power_off_machine()

        # do auto boot if possible
        if board_version is None:
            raise exceptions.ConfigurationException(
                "Please set a machine version number in the configuration "
                "file (spynnaker.cfg or pacman.cfg)")
        txrx.ensure_board_is_ready(
            enable_reinjector=enable_reinjection)
        txrx.discover_scamp_connections()
        machine = txrx.get_machine_details()

        return machine, txrx

    @staticmethod
    def _sort_out_scamp_connections(scamp_connections_data):
        scamp_addresses = list()
        for scamp_connection in scamp_connections_data.split(":"):
            scamp_connection_split = scamp_connection.split(",")
            if len(scamp_connection_split) == 3:
                scamp_addresses.append(SocketAddressWithChip(
                    hostname=scamp_connection_split[0],
                    port_num=None,
                    chip_x=int(scamp_connection_split[1]),
                    chip_y=int(scamp_connection_split[2])))
            else:
                scamp_addresses.append(SocketAddressWithChip(
                    hostname=scamp_connection_split[0],
                    port_num=int(scamp_connection_split[1]),
                    chip_x=int(scamp_connection_split[2]),
                    chip_y=int(scamp_connection_split[3])))
        return scamp_addresses

    @staticmethod
    def _sort_out_bmp_cabinet_and_frame_string(bmp_cabinet_and_frame):
        split_string = bmp_cabinet_and_frame.split(";", 2)
        if len(split_string) == 1:
            hostname_split = split_string[0].split(",")
            if len(hostname_split) == 1:
                return [0, 0, split_string[0], None]
            else:
                return [0, 0, hostname_split[0], hostname_split[1]]
        if len(split_string) == 2:
            hostname_split = split_string[1].split(",")
            if len(hostname_split) == 1:
                return [0, split_string[0], split_string[1], None]
            else:
                return [0, split_string[0], hostname_split[0],
                        hostname_split[1]]
        hostname_split = split_string[2].split(",")
        if len(hostname_split) == 1:
            return [split_string[0], split_string[1], hostname_split[0], None]
        else:
            return [split_string[0], split_string[1], hostname_split[0],
                    hostname_split[1]]

    @staticmethod
    def _sort_out_bmp_boards_string(bmp_boards):

        # If the string is a range of boards, get the range
        range_match = re.match("(\d+)-(\d+)", bmp_boards)
        if range_match is not None:
            return range(int(range_match.group(1)),
                         int(range_match.group(2)) + 1)

        # Otherwise, assume a list of boards
        return [int(board) for board in bmp_boards.split(",")]

    def _sort_out_bmp_string(self, bmp_string):
        """ Take a BMP line and split it into the BMP connection data

        :param bmp_string: the BMP string to be converted
        :return: the BMP connection data
        """
        bmp_details = list()
        if bmp_string is None or bmp_string == "None":
            return None

        for bmp_detail in bmp_string.split(":"):

            bmp_string_split = bmp_detail.split("/")
            (cabinet, frame, hostname, port_num) = \
                self._sort_out_bmp_cabinet_and_frame_string(
                    bmp_string_split[0])

            if len(bmp_string_split) == 1:

                # if there is no split, then assume its one board,
                # located at position 0
                if port_num is not None:
                    bmp_details.append(
                        BMPConnectionData(cabinet, frame, hostname, [0],
                                          int(port_num)))
                else:
                    bmp_details.append(
                        BMPConnectionData(cabinet, frame, hostname, [0],
                                          port_num=None))
            else:
                boards = self._sort_out_bmp_boards_string(bmp_string_split[1])
                if port_num is not None:
                    bmp_details.append(
                        BMPConnectionData(cabinet, frame, hostname, boards,
                                          int(port_num)))
                else:
                    bmp_details.append(
                        BMPConnectionData(cabinet, frame, hostname, boards,
                                          None))
        return bmp_details
