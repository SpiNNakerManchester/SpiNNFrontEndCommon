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
from spinn_front_end_common.utilities.utility_objs.extra_monitor_scp_messages\
    import (
        SetRouterTimeoutMessage)


class SetRouterTimeoutProcess(AbstractMultiConnectionProcess):
    """ How to send messages to set router timeouts. These messages need to be\
        sent to cores running the extra monitor binary.

    .. note::
        SCAMP sets wait2 to zero by default!

    .. note::
        Timeouts are specified in a weird floating point format.
        See the SpiNNaker datasheet for details.
    """

    def set_wait1_timeout(self, mantissa, exponent, core_subsets):
        """ The wait1 timeout is the time from when a packet is received to\
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
        """ The wait2 timeout is the time from when a packet has emergency\
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
        """ Set a timeout for a router controlled by an extra monitor on a\
            core. This is not a parallelised operation in order to aid\
            debugging when it fails.

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
