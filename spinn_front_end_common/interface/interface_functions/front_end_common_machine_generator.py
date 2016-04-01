# spinnman imports
from spinnman.connections.socket_address_with_chip import SocketAddressWithChip
from spinnman.transceiver import create_transceiver_from_hostname
from spinnman.model.core_subsets import CoreSubsets
from spinnman.model.core_subset import CoreSubset
from spinnman.model.bmp_connection_data import BMPConnectionData

# front end common imports
from spinn_front_end_common.utilities import exceptions

# general imports
import re


class FrontEndCommonMachineGenerator(object):
    """ Interface to make a transceiver and a spinn_machine object
    """

    def __call__(
            self, hostname, bmp_details, downed_chips, downed_cores,
            board_version, number_of_boards, width, height, auto_detect_bmp,
            enable_reinjection, scamp_connection_data, boot_port_num,
            reset_machine_on_start_up, max_sdram_size=None):

        """
        :param hostname: the hostname or ip address of the spinnaker machine
        :param bmp_details: the details of the BMP connections
        :param downed_chips: the chips that are down which SARK thinks are\
                alive
        :param downed_cores: the cores that are down which SARK thinks are\
                alive
        :param board_version: the version of the boards being used within the\
                machine (1, 2, 3, 4 or 5)
        :param number_of_boards: the number of boards within the machine
        :param width: The width of the machine in chips
        :param height: The height of the machine in chips
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
        :return: None
        """

        # if the end user gives you scamp data, use it and don't discover them
        if scamp_connection_data is not None:
            scamp_connection_data = \
                self._sort_out_scamp_connections(scamp_connection_data)

        # sort out down chips and down cores if needed
        ignored_chips, ignored_cores = \
            self._sort_out_downed_chips_cores(downed_chips, downed_cores)

        # sort out BMP connections into list of strings
        bmp_connection_data = self._sort_out_bmp_string(bmp_details)

        txrx = create_transceiver_from_hostname(
            hostname=hostname, bmp_connection_data=bmp_connection_data,
            version=board_version, ignore_chips=ignored_chips,
            ignore_cores=ignored_cores, number_of_boards=number_of_boards,
            auto_detect_bmp=auto_detect_bmp, boot_port_no=boot_port_num,
            scamp_connections=scamp_connection_data,
            max_sdram_size=max_sdram_size)

        if reset_machine_on_start_up:
            txrx.power_off_machine()

        # update number of boards from machine
        if number_of_boards is None:
            number_of_boards = txrx.number_of_boards_located

        # do auto boot if possible
        if board_version is None:
            raise exceptions.ConfigurationException(
                "Please set a machine version number in the configuration "
                "file (spynnaker.cfg or pacman.cfg)")
        txrx.ensure_board_is_ready(
            number_of_boards, width, height,
            enable_reinjector=enable_reinjection)
        txrx.discover_scamp_connections()
        machine = txrx.get_machine_details()

        return {"machine": machine, "txrx": txrx}

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

    @staticmethod
    def _sort_out_downed_chips_cores(downed_chips, downed_cores):
        """ Translate the down cores and down chips string into a form that \
            spinnman can understand

        :param downed_cores: string representing down cores
        :type downed_cores: str
        :param downed_chips: string representing down chips
        :type: downed_chips: str
        :return: a list of down cores and down chips in processor and \
                core subset format
        """
        ignored_chips = None
        ignored_cores = None
        if downed_chips is not None and downed_chips != "None":
            ignored_chips = CoreSubsets()
            for downed_chip in downed_chips.split(":"):
                x, y = downed_chip.split(",")
                ignored_chips.add_core_subset(CoreSubset(int(x), int(y),
                                                         []))
        if downed_cores is not None and downed_cores != "None":
            ignored_cores = CoreSubsets()
            for downed_core in downed_cores.split(":"):
                x, y, processor_id = downed_core.split(",")
                ignored_cores.add_processor(int(x), int(y),
                                            int(processor_id))
        return ignored_chips, ignored_cores
