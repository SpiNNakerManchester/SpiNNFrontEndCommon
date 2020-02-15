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
from spinn_front_end_common.interface.buffer_management import BufferManager
from spinn_front_end_common.interface.buffer_management.buffer_models \
    import (
        AbstractSendsBuffersFromHost, AbstractReceiveBuffersToHost)


class BufferManagerCreator(object):
    __slots__ = []

    def __call__(
            self, placements, tags, txrx,
            uses_advanced_monitors, report_folder, extra_monitor_cores=None,
            extra_monitor_to_chip_mapping=None,
            packet_gather_cores_to_ethernet_connection_map=None, machine=None,
            fixed_routes=None, java_caller=None):
        """
        :param placements:
        :param tags:
        :param txrx:
        :param uses_advanced_monitors:
        :param extra_monitor_cores:
        :param extra_monitor_to_chip_mapping:
        :param packet_gather_cores_to_ethernet_connection_map:
        :param machine:
        :param fixed_routes:
        :param report_folder: The path where \
            the SQLite database holding the data will be placed, \
            and where any java provenance can be written.
        :type report_folder: str
        :return:
        """
        # pylint: disable=too-many-arguments
        progress = ProgressBar(placements.n_placements, "Initialising buffers")

        # Create the buffer manager
        buffer_manager = BufferManager(
            placements=placements, tags=tags, transceiver=txrx,
            extra_monitor_cores=extra_monitor_cores,
            packet_gather_cores_to_ethernet_connection_map=(
                packet_gather_cores_to_ethernet_connection_map),
            extra_monitor_to_chip_mapping=extra_monitor_to_chip_mapping,
            machine=machine, uses_advanced_monitors=uses_advanced_monitors,
            fixed_routes=fixed_routes, report_folder=report_folder,
            java_caller=java_caller)

        for placement in progress.over(placements.placements):
            if isinstance(placement.vertex, AbstractSendsBuffersFromHost):
                if placement.vertex.buffering_input():
                    buffer_manager.add_sender_vertex(placement.vertex)

            if isinstance(placement.vertex, AbstractReceiveBuffersToHost):
                buffer_manager.add_receiving_vertex(placement.vertex)

        return buffer_manager
