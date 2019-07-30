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

from spinn_front_end_common.utilities.utility_objs.extra_monitor_scp_messages\
    import (
        SetReinjectionPacketTypesMessage)
from spinnman.processes import AbstractMultiConnectionProcess


class SetPacketTypesProcess(AbstractMultiConnectionProcess):
    def __init__(self, connection_selector):
        super(SetPacketTypesProcess, self).__init__(connection_selector)

    def set_packet_types(self, core_subsets, point_to_point, multicast,
                         nearest_neighbour, fixed_route):
        """ Set what types of packets should be reinjected.

        :param core_subsets: sets of cores to send command to
        :param point_to_point: If point-to-point should be set
        :type point_to_point: bool
        :param multicast: If multicast should be set
        :type multicast: bool
        :param nearest_neighbour: If nearest neighbour should be set
        :type nearest_neighbour: bool
        :param fixed_route: If fixed route should be set
        :type fixed_route: bool
        :param command_code: The SCP command code
        :rtype: None
        """
        # pylint: disable=too-many-arguments
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(SetReinjectionPacketTypesMessage(
                    core_subset.x, core_subset.y, processor_id, multicast,
                    point_to_point, fixed_route, nearest_neighbour))
        self._finish()
        self.check_for_error()
