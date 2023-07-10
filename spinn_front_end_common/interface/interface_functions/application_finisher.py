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
from spinnman.messages.scp.enums import Signal
from spinnman.model.enums import CPUState, ExecutableType
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import (
    ExecutableFailedToStopException)

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

        successful_cores_finished = txrx.get_cpu_infos(
            all_core_subsets, CPUState.FINISHED, True)

        txrx.send_signal(app_id, Signal.SYNC0)
        txrx.send_signal(app_id, Signal.SYNC1)

        for core_subset in all_core_subsets:
            for processor in core_subset.processor_ids:
                if not successful_cores_finished.is_core(
                        core_subset.x, core_subset.y, processor):
                    txrx.update_provenance_and_exit(
                        core_subset.x, core_subset.y, processor)
        time.sleep(0.5)

        processors_finished = txrx.get_core_state_count(
            app_id, CPUState.FINISHED)

    progress.end()
