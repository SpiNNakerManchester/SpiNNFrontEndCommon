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

from spinnman.exceptions import (
    SpinnmanException, SpiNNManCoresNotInStateException)
from spinnman.messages.scp.enums import Signal
from spinnman.model import ExecutableTargets
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities.iobuf_extractor import IOBufExtractor


def run_system_application(
        executable_cores, app_id,
        read_algorithm_iobuf, check_for_success_function,
        cpu_end_states, needs_sync_barrier, filename_template,
        binaries_to_track=None, progress_bar=None, logger=None, timeout=None):
    """
    Executes the given _system_ application.
    Used for on-chip expanders, compressors, etc.

    :param ~spinnman.model.ExecutableTargets executable_cores:
        the cores to run the executable on.
    :param int app_id: the app-id for the executable
    :param bool read_algorithm_iobuf: whether to report IOBUFs
    :param callable check_for_success_function:
        function used to check success;
        expects `executable_cores`, `transceiver` as inputs
    :param set(~spinnman.model.enums.CPUState) cpu_end_states:
        the states that a successful run is expected to terminate in
    :param bool needs_sync_barrier: whether a sync barrier is needed
    :param str filename_template: the IOBUF filename template.
    :param list(str) binaries_to_track:
        A list of binary names to check for exit state.
        Or `None` for all binaries
    :param progress_bar: Possible progress bar to update.
           end() will be called after state checked
    :type progress_bar: ~spinn_utilities.progress_bar.ProgressBar or None
    :param ~logging.Logger logger:
        If provided and IOBUF is extracted, will be used to log errors and
        warnings
    :param timeout:
        Number of seconds to wait before force stopping, or `None` to wait
        forever
    :type timeout: float or None
    :raise SpinnmanException:
        If one should arise from the underlying SpiNNMan calls
    """
    transceiver = FecDataView.get_transceiver()
    # load the executable
    transceiver.execute_application(executable_cores, app_id)

    if needs_sync_barrier:

        # fire all signals as required
        transceiver.send_signal(app_id, Signal.SYNC0)

    error = None
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
        if progress_bar is not None:
            progress_bar.end()
        succeeded = True
    except SpiNNManCoresNotInStateException as ex:
        error = ex
        core_state_string = transceiver.get_core_status_string(
            ex.failed_core_states())
    except SpinnmanException as ex:
        # Delay the exception until iobuf is ready
        error = ex

    if progress_bar is not None:
        progress_bar.end()

    # Check if any cores have not completed successfully
    if succeeded and check_for_success_function:
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
        raise error  # pylint: disable=raising-bad-type


def _report_iobuf_messages(cores, logger, filename_template):
    """
    :param ~spinnman.model.ExecutableTargets cores:
    :param ~logging.Logger logger:
    :param str filename_template:
    """
    # Import in this function to prevent circular import issue
    iobuf_reader = IOBufExtractor(
        cores,
        filename_template=filename_template, suppress_progress=False)
    error_entries, warn_entries = iobuf_reader.extract_iobuf()
    if logger is not None:
        for entry in warn_entries:
            logger.warn(entry)
        for entry in error_entries:
            logger.error(entry)
