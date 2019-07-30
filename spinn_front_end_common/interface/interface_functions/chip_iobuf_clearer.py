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

from spinn_front_end_common.utilities.scp import ClearIOBUFProcess
from spinn_front_end_common.utilities.utility_objs import ExecutableType


class ChipIOBufClearer(object):
    """ Clears the logging output buffer of an application running on a\
        SpiNNaker machine.
    """

    __slots__ = []

    def __call__(self, transceiver, executable_types):

        core_subsets = \
            executable_types[ExecutableType.USES_SIMULATION_INTERFACE]

        process = ClearIOBUFProcess(transceiver.scamp_connection_selector)
        process.clear_iobuf(core_subsets, len(core_subsets))
