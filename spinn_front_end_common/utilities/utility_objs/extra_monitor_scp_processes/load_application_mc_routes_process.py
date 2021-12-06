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

from spinnman.processes import AbstractMultiConnectionProcess
from spinn_front_end_common.utilities.utility_objs.\
    extra_monitor_scp_messages import (
        LoadApplicationMCRoutesMessage)


class LoadApplicationMCRoutesProcess(AbstractMultiConnectionProcess):
    """ How to send messages to load the saved application multicast routing\
        tables.
    """

    def load_application_mc_routes(self, core_subsets):
        """
        :param ~spinn_machine.CoreSubsets core_subsets:
            sets of cores to send command to
        """
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(LoadApplicationMCRoutesMessage(
                    core_subset.x, core_subset.y, processor_id))
        self._finish()
        self.check_for_error()
