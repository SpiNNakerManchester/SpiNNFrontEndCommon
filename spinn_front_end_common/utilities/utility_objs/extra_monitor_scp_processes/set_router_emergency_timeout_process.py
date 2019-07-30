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
        SetRouterEmergencyTimeoutMessage)
from spinnman.processes import AbstractMultiConnectionProcess


class SetRouterEmergencyTimeoutProcess(AbstractMultiConnectionProcess):
    def __init__(self, connection_selector):
        super(SetRouterEmergencyTimeoutProcess, self).__init__(
            connection_selector)

    def set_timeout(self, mantissa, exponent, core_subsets):
        for core in core_subsets.core_subsets:
            for processor_id in core.processor_ids:
                self._set_timeout(core, processor_id, mantissa, exponent)

    def _set_timeout(self, core, processor_id, mantissa, exponent):
        self._send_request(SetRouterEmergencyTimeoutMessage(
            core.x, core.y, processor_id, mantissa, exponent))
        self._finish()
        self.check_for_error()
