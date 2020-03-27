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

import struct
from spinn_utilities.progress_bar import ProgressBar
from spinnman.messages.sdp import SDPHeader, SDPFlag
from spinnman.messages.scp.abstract_messages import AbstractSCPRequest
from spinnman.messages.scp import SCPRequestHeader
from spinnman.messages.scp.impl import CheckOKResponse
from spinnman.processes import AbstractMultiConnectionProcess
from spinn_front_end_common.utilities.constants import (
    SDP_PORTS, SDP_RUNNING_MESSAGE_CODES)
from spinn_utilities.overrides import overrides


class _UpdateRuntimeRequest(AbstractSCPRequest):
    def __init__(self, x, y, p, current_time, run_time, infinite_run):
        """
        :param int x:
        :param int y:
        :param int p:
        :param int current_time:
        :param int run_time:
        :param bool infinite_run:
        """
        # pylint: disable=too-many-arguments
        sdp_flags = SDPFlag.REPLY_EXPECTED

        super(_UpdateRuntimeRequest, self).__init__(
            SDPHeader(
                flags=sdp_flags,
                destination_port=SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value,
                destination_cpu=p, destination_chip_x=x, destination_chip_y=y),
            SCPRequestHeader(
                command=SDP_RUNNING_MESSAGE_CODES.SDP_NEW_RUNTIME_ID_CODE),
            argument_1=run_time, argument_2=infinite_run,
            argument_3=current_time,
            data=struct.pack("<B", int(True)))

    @overrides(AbstractSCPRequest.get_scp_response)
    def get_scp_response(self):
        return CheckOKResponse(
            "update runtime",
            SDP_RUNNING_MESSAGE_CODES.SDP_NEW_RUNTIME_ID_CODE.value)


class UpdateRuntimeProcess(AbstractMultiConnectionProcess):
    """ How to update the target running time of a set of cores.

    .. note::
        The cores must be using the simulation interface.
    """

    def __init__(self, connection_selector):
        """
        :param connection_selector:
        :type connection_selector:
            ~spinnman.processes.abstract_multi_connection_process_connection_selector.AbstractMultiConnectionProcessConnectionSelector
        """
        super(UpdateRuntimeProcess, self).__init__(connection_selector)
        self._progress = None

    def __receive_response(self, _response):
        if self._progress is not None:
            self._progress.update()

    def update_runtime(self, current_time, run_time, infinite_run,
                       core_subsets, n_cores=None):
        """
        :param int current_time:
        :param int run_time:
        :param bool infinite_run:
        :param ~spinn_machine.CoreSubsets core_subsets:
        :param int n_cores: Defaults to the number of cores in `core_subsets`.
        """
        if n_cores is None:
            n_cores = len(core_subsets)
        self._progress = ProgressBar(n_cores, "Updating run time")
        for core_subset in core_subsets:
            for processor_id in core_subset.processor_ids:
                self._send_request(
                    _UpdateRuntimeRequest(
                        core_subset.x, core_subset.y, processor_id,
                        current_time, run_time, infinite_run),
                    callback=self.__receive_response)
        self._finish()
        self._progress.end()
        self._progress = None
        self.check_for_error()
