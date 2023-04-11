# Copyright (c) 2017 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
    """
    How to send messages to read the status of extra monitors.
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
