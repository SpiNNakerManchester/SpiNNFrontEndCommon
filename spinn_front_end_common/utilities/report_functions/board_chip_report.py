# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
from spinn_utilities.progress_bar import ProgressBar
from .utils import ReportFile


class BoardChipReport(object):
    """ Report on what chips are on the machine.
    """

    AREA_CODE_REPORT_NAME = "board_chip_report.txt"

    def __call__(self, report_default_directory, machine):
        """ Creates a report that states where the chips are on the actual \
            board we ran on.

        :param str report_default_directory:
            the folder where reports are written
        :param ~spinn_machine.Machine machine:
            python representation of the machine
        """
        # create the progress bar for end users
        progress_bar = ProgressBar(
            len(machine.ethernet_connected_chips),
            "Writing the board chip report")

        # iterate over ethernet chips and then the chips on that board
        with ReportFile(report_default_directory,
                        self.AREA_CODE_REPORT_NAME) as writer:
            self._write_report(writer, machine, progress_bar)

    @staticmethod
    def _write_report(writer, machine, progress_bar):
        """
        :param ~io.FileIO writer:
        :param ~spinn_machine.Machine machine:
        :param ~spinn_utilities.progress_bar.ProgressBar progress_bar:
        """
        for chip in progress_bar.over(machine.ethernet_connected_chips):
            writer.write(
                f"board with IP address : {chip.ip_address} : has "
                f"chips {list(machine.get_existing_xys_on_board(chip))}\n")
