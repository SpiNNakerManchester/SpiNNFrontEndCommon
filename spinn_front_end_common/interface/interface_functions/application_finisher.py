# Copyright (c) 2015 The University of Manchester
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

import struct
import time
from spinn_utilities.progress_bar import ProgressBar
from spinnman.messages.sdp import SDPFlag, SDPHeader, SDPMessage
from spinnman.messages.scp.enums import Signal
from spinnman.model.enums import CPUState
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.constants import (
    SDP_PORTS, SDP_RUNNING_MESSAGE_CODES)
from spinn_front_end_common.utilities.exceptions import (
    ExecutableFailedToStopException)
from spinn_front_end_common.utilities.utility_objs import ExecutableType

_ONE_WORD = struct.Struct("<I")


def application_finisher():
    """
    Handles finishing the running of an application, collecting the
    status of the cores that the application was running on.

    :raises ExecutableFailedToStopException:
    """
    app_id = FecDataView.get_app_id()
    txrx = FecDataView.get_transceiver()
    all_core_subsets = FecDataView.get_executable_types()[
        ExecutableType.USES_SIMULATION_INTERFACE]
    total_processors = len(all_core_subsets)

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
                f"{processors_rte + processors_watchdogged} of "
                f"{total_processors} processors went into an error state "
                "when shutting down")

        successful_cores_finished = txrx.get_cores_in_state(
            all_core_subsets, CPUState.FINISHED)

        for core_subset in all_core_subsets:
            for processor in core_subset.processor_ids:
                if not successful_cores_finished.is_core(
                        core_subset.x, core_subset.y, processor):
                    _update_provenance_and_exit(
                        txrx, app_id, processor, core_subset)
        time.sleep(0.5)

        processors_finished = txrx.get_core_state_count(
            app_id, CPUState.FINISHED)

    progress.end()


def _update_provenance_and_exit(txrx, app_id, processor, core_subset):
    """
    :param ~spinnman.transceiver.Transceiver txrx:
    :param int processor:
    :param ~.CoreSubset core_subset:
    """
    byte_data = _ONE_WORD.pack(
        SDP_RUNNING_MESSAGE_CODES
        .SDP_UPDATE_PROVENCE_REGION_AND_EXIT.value)
    # Send these signals to make sure the application isn't stuck
    txrx.send_signal(app_id, Signal.SYNC0)
    txrx.send_signal(app_id, Signal.SYNC1)
    txrx.send_sdp_message(SDPMessage(
        sdp_header=SDPHeader(
            flags=SDPFlag.REPLY_NOT_EXPECTED,
            destination_port=SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value,
            destination_cpu=processor,
            destination_chip_x=core_subset.x,
            destination_chip_y=core_subset.y),
        data=byte_data))
