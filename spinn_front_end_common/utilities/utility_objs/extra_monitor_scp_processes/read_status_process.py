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
        GetReinjectionStatusMessage)
from spinnman.processes import AbstractMultiConnectionProcess


class ReadStatusProcess(AbstractMultiConnectionProcess):
    def __init__(self, connection_selector):
        super(ReadStatusProcess, self).__init__(connection_selector)
        self._reinjection_status = dict()

    def handle_reinjection_status_response(self, response):
        status = response.reinjection_functionality_status
        self._reinjection_status[(response.sdp_header.source_chip_x,
                                  response.sdp_header.source_chip_y)] = status

    def get_reinjection_status(self, x, y, p):
        self._reinjection_status = dict()
        self._send_request(GetReinjectionStatusMessage(x, y, p),
                           callback=self.handle_reinjection_status_response)
        self._finish()
        self.check_for_error()
        return self._reinjection_status[(x, y)]

    def get_reinjection_status_for_core_subsets(
            self, core_subsets):
        self._reinjection_status = dict()
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(GetReinjectionStatusMessage(
                    core_subset.x, core_subset.y, processor_id),
                    callback=self.handle_reinjection_status_response)
        self._finish()
        self.check_for_error()
        return self._reinjection_status
