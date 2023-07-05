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
from spinn_machine import CoreSubsets, CoreSubset
from spinnman.messages.sdp import SDPFlag, SDPHeader, SDPMessage
from spinnman.messages.scp.enums import Signal
from spinnman.model.enums import CPUState, ExecutableType
from spinnman.transceiver import Transceiver
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.constants import (
    SDP_PORTS, SDP_RUNNING_MESSAGE_CODES)
from spinn_front_end_common.utilities.exceptions import (
    ExecutableFailedToStopException)

_ONE_WORD = struct.Struct("<I")


def application_finisher() -> None:
    """
    Handles finishing the running of an application, collecting the
    status of the cores that the application was running on.

    :raises ExecutableFailedToStopException:
    """
    app_id = FecDataView.get_app_id()
    txrx = FecDataView.get_transceiver()
    all_core_subsets = FecDataView.get_cores_for_type(
        ExecutableType.USES_SIMULATION_INTERFACE)
    total_processors = len(all_core_subsets)

    with ProgressBar(
            total_processors,
            "Turning off all the cores within the simulation") as progress:
        # check that the right number of processors are finished
        processors_finished = txrx.get_core_state_count(
            app_id, CPUState.FINISHED)
        finished_cores = 0

        while processors_finished != total_processors:
            if processors_finished > finished_cores:
                progress.update(processors_finished - finished_cores)
                finished_cores = processors_finished

            _detect_fails(txrx, app_id, total_processors)
            _detect_finished(txrx, app_id, all_core_subsets)
            time.sleep(0.5)
            processors_finished = txrx.get_core_state_count(
                app_id, CPUState.FINISHED)


def _detect_fails(txrx: Transceiver, app_id: int, n_cores: int):
    """
    :param ~spinnman.transceiver.Transceiver txrx:
    :param int app_id:
    :param int n_cores:
    """
    cores_rte = txrx.get_core_state_count(app_id, CPUState.RUN_TIME_EXCEPTION)
    cores_watchdogged = txrx.get_core_state_count(app_id, CPUState.WATCHDOG)

    if cores_rte > 0 or cores_watchdogged > 0:
        raise ExecutableFailedToStopException(
            f"{cores_rte + cores_watchdogged} of {n_cores} processors went "
            "into an error state when shutting down")


def _detect_finished(txrx: Transceiver, app_id: int, all_cores: CoreSubsets):
    """
    :param ~spinnman.transceiver.Transceiver txrx:
    :param int app_id:
    :param ~.CoreSubsets all_cores:
    """
    successful_cores_finished = txrx.get_cores_in_state(
        all_cores, CPUState.FINISHED)

    for core_subset in all_cores:
        for processor in core_subset.processor_ids:
            if not successful_cores_finished.is_core(
                    core_subset.x, core_subset.y, processor):
                _update_provenance_and_exit(
                    txrx, app_id, processor, core_subset)


def _update_provenance_and_exit(
        txrx: Transceiver, app_id: int, processor: int,
        core_subset: CoreSubset):
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
