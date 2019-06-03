import os
from spinn_utilities.progress_bar import ProgressBar


class BoardChipReport(object):
    """ Report on memory usage
    """

    AREA_CODE_REPORT_NAME = "board_chip_report.txt"

    def __call__(self, report_default_directory, machine):
        """ Creates a report that states where in SDRAM each region is.

        :param report_default_directory: the folder where reports are written
        :param machine: python representation of the machine
        :rtype: None
        """

        # create file path
        directory_name = os.path.join(
            report_default_directory, self.AREA_CODE_REPORT_NAME)

        # create the progress bar for end users
        progress_bar = ProgressBar(
            len(machine.ethernet_connected_chips),
            "Writing the board chip report")

        # iterate over ethernet chips and then the chips on that board
        with open(directory_name, "w") as writer:
            for ethernet_connected_chip in \
                    progress_bar.over(machine.ethernet_connected_chips):
                xys = machine.get_existing_xys_on_board(
                    ethernet_connected_chip)
                writer.write(
                    "board with IP address : {} : has chips {}\n".format(
                        ethernet_connected_chip.ip_address, list(xys)))
