# Copyright (c) 2019 The University of Manchester
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
import time
from typing import Callable, FrozenSet, List, Optional
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from spinnman.exceptions import (
    SpinnmanException, SpiNNManCoresNotInStateException)
from spinnman.messages.scp.enums import Signal
from spinnman.model import ExecutableTargets
from spinnman.model.enums import CPUState, ExecutableType
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.iobuf_extractor import IOBufExtractor


def run_system_application(
        executable_cores: ExecutableTargets, app_id: int,
        read_algorithm_iobuf: bool,
        check_for_success_function: Optional[
            Callable[[ExecutableTargets], bool]],
        cpu_end_states: FrozenSet[CPUState], needs_sync_barrier: bool,
        filename_template: str, binaries_to_track: Optional[List[str]] = None,
        progress_bar: Optional[ProgressBar] = None,
        logger: Optional[FormatAdapter] = None,
        timeout: Optional[float] = None) -> None:
    """
    Executes the given _system_ application.
    Used for on-chip expander, compressors, etc.

    :param executable_cores: the cores to run the executable on.
    :param app_id: the app-id for the executable
    :param read_algorithm_iobuf: whether to report IOBUFs
    :param check_for_success_function:
        function used to check success;
        expects `executable_cores`, `transceiver` as inputs
    :param cpu_end_states:
        the states that a successful run is expected to terminate in
    :param needs_sync_barrier: whether a sync barrier is needed
    :param filename_template: the IOBUF filename template.
    :param binaries_to_track:
        A list of binary names to check for exit state.
        Or `None` for all binaries
    :param progress_bar: Possible progress bar to update.
           end() will be called after state checked
    :param logger:
        If provided and IOBUF is extracted, will be used to log errors and
        warnings
    :param timeout:
        Number of seconds to wait before force stopping, or `None` to wait
        forever
    :raise SpinnmanException:
        If one should arise from the underlying SpiNNMan calls
    """
    transceiver = FecDataView.get_transceiver()
    # load the executable
    _load_application(executable_cores, app_id)

    if needs_sync_barrier:
        # fire all signals as required
        transceiver.send_signal(app_id, Signal.SYNC0)

    error: Optional[Exception] = None
    binary_start_types = dict()
    if binaries_to_track is None:
        check_targets = executable_cores
    else:
        check_targets = ExecutableTargets()
        for binary_name in binaries_to_track:
            check_targets.add_subsets(
                binary_name,
                executable_cores.get_cores_for_binary(binary_name))
    for binary_name in executable_cores.binaries:
        binary_start_types[binary_name] = ExecutableType.SYSTEM

    # Wait for the executable to finish
    succeeded = False
    core_state_string = None
    try:
        transceiver.wait_for_cores_to_be_in_state(
            check_targets.all_core_subsets, app_id, cpu_end_states,
            progress_bar=progress_bar, timeout=timeout)
        succeeded = True
    except SpiNNManCoresNotInStateException as ex:
        error = ex
        core_state_string = ex.failed_core_states().get_status_string()
    except SpinnmanException as ex:
        # Delay the exception until iobuf is ready
        error = ex

    if progress_bar is not None:
        progress_bar.end()

    # Check if any cores have not completed successfully
    if succeeded and check_for_success_function is not None:
        succeeded = check_for_success_function(executable_cores)

    # if doing iobuf or on failure (succeeded is None is not failure)
    if read_algorithm_iobuf or not succeeded:
        _report_iobuf_messages(executable_cores, logger, filename_template)

    # stop anything that's associated with the compressor binary
    transceiver.stop_application(app_id)
    FecDataView.free_id(app_id)

    if error is not None:
        if core_state_string is not None:
            print(core_state_string)
        raise error


def _report_iobuf_messages(
        cores: ExecutableTargets, logger: Optional[FormatAdapter],
        filename_template: str) -> None:
    # Import in this function to prevent circular import issue
    iobuf_reader = IOBufExtractor(
        cores,
        filename_template=filename_template, suppress_progress=False)
    error_entries, warn_entries = iobuf_reader.extract_iobuf()
    if logger is not None:
        for entry in warn_entries:
            logger.warning("{}", entry)
        for entry in error_entries:
            logger.error("{}", entry)


def _load_application(
        executable_targets: ExecutableTargets, app_id: int) -> None:
    """
    Execute a set of binaries that make up a complete application on
    specified cores, wait for them to be ready and then start all of the
    binaries.

    .. note::
        This will get the binaries into c_main but will not signal the
        barrier.

    :param executable_targets:
        The binaries to be executed and the cores to execute them on
    :param app_id: The app_id to give this application
    """
    # Execute each of the binaries and get them in to a "wait" state
    transceiver = FecDataView.get_transceiver()
    for binary in executable_targets.binaries:
        core_subsets = executable_targets.get_cores_for_binary(binary)
        transceiver.execute_flood(core_subsets, binary, app_id, wait=True)

    # Sleep to allow cores to get going
    time.sleep(0.5)

    # Check that the binaries have reached a wait state
    count = transceiver.get_core_state_count(app_id, CPUState.READY)
    if count < executable_targets.total_processors:
        cores_ready = transceiver.get_cpu_infos(
            executable_targets.all_core_subsets, CPUState.READY, include=False)
        if len(cores_ready) > 0:
            raise SpinnmanException(
                f"Only {count} of {executable_targets.total_processors} "
                "cores reached ready state: "
                f"{cores_ready.get_status_string()}")

    # Send a signal telling the application to start
    transceiver.send_signal(app_id, Signal.START)
