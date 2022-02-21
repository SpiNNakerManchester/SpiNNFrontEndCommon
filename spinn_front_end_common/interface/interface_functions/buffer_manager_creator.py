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
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.buffer_management import BufferManager
from spinn_front_end_common.interface.buffer_management.buffer_models \
    import (
        AbstractSendsBuffersFromHost, AbstractReceiveBuffersToHost)


def buffer_manager_creator(
        extra_monitor_to_chip_mapping=None,
        packet_gather_cores_to_ethernet_connection_map=None):
    """ Creates a buffer manager.

    :param bool uses_advanced_monitors:
    :param extra_monitor_to_chip_mapping:
    :type extra_monitor_to_chip_mapping:
        dict(tuple(int,int),ExtraMonitorSupportMachineVertex)
    :param packet_gather_cores_to_ethernet_connection_map:
    :type packet_gather_cores_to_ethernet_connection_map:
        dict(tuple(int,int),DataSpeedUpPacketGatherMachineVertex)
    :rtype: BufferManager
    """
    placements = FecDataView.get_placements()
    # pylint: disable=too-many-arguments
    progress = ProgressBar(placements.n_placements, "Initialising buffers")

    # Create the buffer manager
    buffer_manager = BufferManager(
        packet_gather_cores_to_ethernet_connection_map=(
            packet_gather_cores_to_ethernet_connection_map),
        extra_monitor_to_chip_mapping=extra_monitor_to_chip_mapping)

    for placement in progress.over(placements):
        vertex = placement.vertex
        if isinstance(vertex, AbstractSendsBuffersFromHost) and \
                vertex.buffering_input():
            buffer_manager.add_sender_vertex(vertex)

        if isinstance(vertex, AbstractReceiveBuffersToHost):
            buffer_manager.add_receiving_vertex(vertex)

    return buffer_manager
