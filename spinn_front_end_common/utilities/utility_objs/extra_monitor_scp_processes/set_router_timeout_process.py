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

from spinnman.processes import AbstractMultiConnectionProcess
from spinn_front_end_common.utilities.utility_objs.extra_monitor_scp_messages\
    import (
        SetRouterTimeoutMessage)


class SetRouterTimeoutProcess(AbstractMultiConnectionProcess):
    """
    How to send messages to set router timeouts. These messages need to be
    sent to cores running the extra monitor binary.

    .. note::
        SCAMP sets wait2 to zero by default!

    .. note::
        Timeouts are specified in a weird floating point format.
        See the SpiNNaker datasheet for details.
    """

    def set_wait1_timeout(self, mantissa, exponent, core_subsets):
        """
        The wait1 timeout is the time from when a packet is received to
        when emergency routing becomes enabled.

        :param int mantissa: Timeout mantissa (0 to 15)
        :param int exponent: Timeout exponent (0 to 15)
        :param ~spinn_machine.CoreSubsets core_subsets:
            Where the extra monitors that manage the routers are located.
        """
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self._set_timeout(
                    core_subset, processor_id, mantissa, exponent, wait=1)

    def set_wait2_timeout(self, mantissa, exponent, core_subsets):
        """
        The wait2 timeout is the time from when a packet has emergency
        routing enabled for it to when it is dropped.

        :param int mantissa: Timeout mantissa (0 to 15)
        :param int exponent: Timeout exponent (0 to 15)
        :param ~spinn_machine.CoreSubsets core_subsets:
            Where the extra monitors that manage the routers are located.
        """
        for core_subset in core_subsets.core_subsets:
            for processor_id in core_subset.processor_ids:
                self._set_timeout(
                    core_subset, processor_id, mantissa, exponent, wait=2)

    def _set_timeout(self, core, processor_id, mantissa, exponent, wait):
        """
        Set a timeout for a router controlled by an extra monitor on a core.
        This is not a parallelised operation in order to aid debugging when
        it fails.

        :param ~spinn_machine.CoreSubset core:
        :param int processor_id:
        :param int mantissa:
        :param int exponent:
        :param int wait:
        """
        self._send_request(SetRouterTimeoutMessage(
            core.x, core.y, processor_id,
            timeout_mantissa=mantissa, timeout_exponent=exponent, wait=wait))
        self._finish()
        self.check_for_error()
