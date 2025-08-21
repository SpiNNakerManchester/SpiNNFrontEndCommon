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
from typing import Dict
from spinn_utilities.log import FormatAdapter
from spinn_machine import Chip, CoreSubsets, CoreSubset
from spinnman.processes import AbstractMultiConnectionProcess
from spinn_front_end_common.utilities.utility_objs import ReInjectionStatus
from spinn_front_end_common.utilities.utility_objs.extra_monitor_scp_messages\
    import (
        ClearReinjectionQueueMessage, ResetCountersMessage,
        GetReinjectionStatusMessage, SetReinjectionPacketTypesMessage,
        SetRouterTimeoutMessage, GetReinjectionStatusMessageResponse)
from spinn_front_end_common.data import FecDataView
logger = FormatAdapter(logging.getLogger(__name__))


class ReinjectorControlProcess(AbstractMultiConnectionProcess):
    """
    How to send messages to the packet reinjection system.
    """
    __slots__ = ()

    def clear_queue(self, core_subsets: CoreSubsets) -> None:
        """
        Clear the reinjection queue.

        :param core_subsets:
        """
        with self._collect_responses():
            for core_subset in core_subsets.core_subsets:
                for processor_id in core_subset.processor_ids:
                    self._send_request(ClearReinjectionQueueMessage(
                        core_subset.x, core_subset.y, processor_id))

    def reset_counters(self, core_subsets: CoreSubsets) -> None:
        """
        Reset the packet counters.

        :param core_subsets:
        """
        with self._collect_responses():
            for core_subset in core_subsets.core_subsets:
                for processor_id in core_subset.processor_ids:
                    self._send_request(ResetCountersMessage(
                        core_subset.x, core_subset.y, processor_id))

    @staticmethod
    def __handle_response(
            result: Dict[Chip, ReInjectionStatus],
            response: GetReinjectionStatusMessageResponse) -> None:
        status = response.reinjection_functionality_status
        header = response.sdp_header
        chip = FecDataView.get_chip_at(
            header.source_chip_x, header.source_chip_y)
        result[chip] = status

    def get_reinjection_status(
            self, x: int, y: int, p: int) -> ReInjectionStatus:
        """
        :param x:
        :param y:
        :param p:
        :returns: The reinjection status of a particular monitor.
        """
        chip = FecDataView.get_chip_at(x, y)
        status: Dict[Chip, ReInjectionStatus] = dict()
        with self._collect_responses():
            self._send_request(
                GetReinjectionStatusMessage(x, y, p),
                functools.partial(self.__handle_response, status))
        return status[chip]

    def get_reinjection_status_for_core_subsets(
            self, core_subsets: CoreSubsets) -> Dict[Chip, ReInjectionStatus]:
        """
        Get the reinjection status of a collection of monitors.

        :param core_subsets:
        :returns: Mapping of the Chips to their reinjection status.
        """
        status: Dict[Chip, ReInjectionStatus] = dict()
        with self._collect_responses(check_error=False):
            for core_subset in core_subsets.core_subsets:
                for processor_id in core_subset.processor_ids:
                    self._send_request(GetReinjectionStatusMessage(
                        core_subset.x, core_subset.y, processor_id),
                        functools.partial(self.__handle_response, status))
        if self.is_error():
            logger.warning("Error(s) reading reinjection status:")
            for (e, tb) in zip(self._exceptions, self._tracebacks):
                traceback.print_exception(type(e), e, tb)
        return status

    def set_packet_types(
            self, core_subsets: CoreSubsets, point_to_point: bool,
            multicast: bool, nearest_neighbour: bool,
            fixed_route: bool) -> None:
        """
        Set what types of packets should be reinjected.

        :param core_subsets: sets of cores to send command to
        :param point_to_point: If point-to-point should be set
        :param multicast: If multicast should be set
        :param nearest_neighbour: If nearest neighbour should be set
        :param fixed_route: If fixed route should be set
        """
        with self._collect_responses():
            for core_subset in core_subsets.core_subsets:
                for processor_id in core_subset.processor_ids:
                    self._send_request(SetReinjectionPacketTypesMessage(
                        core_subset.x, core_subset.y, processor_id, multicast,
                        point_to_point, fixed_route, nearest_neighbour))

    def set_wait1_timeout(self, mantissa: int, exponent: int,
                          core_subsets: CoreSubsets) -> None:
        """
        The wait1 timeout is the time from when a packet is received to
        when emergency routing becomes enabled.

        :param mantissa: Timeout mantissa (0 to 15)
        :param exponent: Timeout exponent (0 to 15)
        :param core_subsets:
            Where the extra monitors that manage the routers are located.
        """
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self.__set_timeout(
                    core_subset, processor_id, mantissa, exponent, wait=1)

    def set_wait2_timeout(self, mantissa: int, exponent: int,
                          core_subsets: CoreSubsets) -> None:
        """
        The wait2 timeout is the time from when a packet has emergency
        routing enabled for it to when it is dropped.

        :param mantissa: Timeout mantissa (0 to 15)
        :param exponent: Timeout exponent (0 to 15)
        :param core_subsets:
            Where the extra monitors that manage the routers are located.
        """
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self.__set_timeout(
                    core_subset, processor_id, mantissa, exponent, wait=2)

    def __set_timeout(
            self, core: CoreSubset, processor_id: int,
            mantissa: int, exponent: int, *, wait: int) -> None:
        """
        Set a timeout for a router controlled by an extra monitor on a core.
        This is not a parallelised operation in order to aid debugging when
        it fails.

        :param core:
        :param processor_id:
        :param mantissa:
        :param exponent:
        :param wait: Which wait to set
        """
        with self._collect_responses():
            self._send_request(SetRouterTimeoutMessage(
                core.x, core.y, processor_id,
                timeout_mantissa=mantissa, timeout_exponent=exponent,
                wait=wait))
