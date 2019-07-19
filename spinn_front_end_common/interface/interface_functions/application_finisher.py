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
import time
from spinn_utilities.progress_bar import ProgressBar
from spinnman.messages.sdp import SDPFlag, SDPHeader, SDPMessage
from spinnman.model.enums import CPUState
from spinn_front_end_common.utilities.constants import (
    SDP_PORTS, SDP_RUNNING_MESSAGE_CODES)
from spinn_front_end_common.utilities.exceptions import (
    ExecutableFailedToStopException)
from spinn_front_end_common.utilities.utility_objs import ExecutableType

_ONE_WORD = struct.Struct("<I")


class ApplicationFinisher(object):
    __slots__ = []

    def __call__(self, app_id, txrx, executable_types):

        total_processors = \
            len(executable_types[ExecutableType.USES_SIMULATION_INTERFACE])
        all_core_subsets = \
            executable_types[ExecutableType.USES_SIMULATION_INTERFACE]

        progress = ProgressBar(
            total_processors,
            "Turning off all the cores within the simulation")

        # check that the right number of processors are finished
        processors_finished = txrx.get_core_state_count(
            app_id, CPUState.FINISHED)
        finished_cores = processors_finished

        while processors_finished != total_processors:
            if processors_finished > finished_cores:
                progress.update(processors_finished - finished_cores)
                finished_cores = processors_finished

            processors_rte = txrx.get_core_state_count(
                app_id, CPUState.RUN_TIME_EXCEPTION)
            processors_watchdogged = txrx.get_core_state_count(
                app_id, CPUState.WATCHDOG)

            if processors_rte > 0 or processors_watchdogged > 0:
                raise ExecutableFailedToStopException(
                    "{} of {} processors went into an error state when"
                    " shutting down".format(
                        processors_rte + processors_watchdogged,
                        total_processors))

            successful_cores_finished = txrx.get_cores_in_state(
                all_core_subsets, CPUState.FINISHED)

            for core_subset in all_core_subsets:
                for processor in core_subset.processor_ids:
                    if not successful_cores_finished.is_core(
                            core_subset.x, core_subset.y, processor):
                        self._update_provenance_and_exit(
                            txrx, processor, core_subset)
            time.sleep(0.5)

            processors_finished = txrx.get_core_state_count(
                app_id, CPUState.FINISHED)

        progress.end()

    @staticmethod
    def _update_provenance_and_exit(txrx, processor, core_subset):
        byte_data = _ONE_WORD.pack(
            SDP_RUNNING_MESSAGE_CODES
            .SDP_UPDATE_PROVENCE_REGION_AND_EXIT.value)

        txrx.send_sdp_message(SDPMessage(
            sdp_header=SDPHeader(
                flags=SDPFlag.REPLY_NOT_EXPECTED,
                destination_port=SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value,
                destination_cpu=processor,
                destination_chip_x=core_subset.x,
                destination_chip_y=core_subset.y),
            data=byte_data))
