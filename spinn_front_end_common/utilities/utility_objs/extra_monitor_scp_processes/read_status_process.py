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

import functools
import logging
import traceback
from spinn_utilities.log import FormatAdapter
from spinnman.processes import AbstractMultiConnectionProcess
from spinn_front_end_common.utilities.utility_objs.extra_monitor_scp_messages\
    import (
        GetReinjectionStatusMessage)

logger = FormatAdapter(logging.getLogger(__name__))


class ReadStatusProcess(AbstractMultiConnectionProcess):
    """ How to send messages to read the status of extra monitors.
    """
    __slots__ = ()

    @staticmethod
    def __handle_response(result, response):
        """
        :param dict result:
        :param GetReinjectionStatusMessageResponse response:
        """
        status = response.reinjection_functionality_status
        header = response.sdp_header
        result[header.source_chip_x, header.source_chip_y] = status

    def get_reinjection_status(self, x, y, p):
        """
        :param int x:
        :param int y:
        :param int p:
        :rtype: ReInjectionStatus
        """
        status = dict()
        self._send_request(GetReinjectionStatusMessage(x, y, p),
                           functools.partial(self.__handle_response, status))
        self._finish()
        self.check_for_error()
        return status[x, y]

    def get_reinjection_status_for_core_subsets(self, core_subsets):
        """
        :param ~spinn_machine.CoreSubsets core_subsets:
        :rtype: dict(tuple(int,int), ReInjectionStatus)
        """
        status = dict()
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(GetReinjectionStatusMessage(
                    core_subset.x, core_subset.y, processor_id),
                    functools.partial(self.__handle_response, status))
        self._finish()
        if self.is_error():
            logger.warning("Error(s) reading reinjection status:")
            for (e, tb) in zip(self._exceptions, self._tracebacks):
                traceback.print_exception(type(e), e, tb)
        return status
