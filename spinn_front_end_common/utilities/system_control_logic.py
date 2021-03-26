# Copyright (c) 2019-2020 The University of Manchester
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

from spinnman.exceptions import SpinnmanException
from spinnman.messages.scp.enums import Signal
from spinnman.model import ExecutableTargets
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities import IOBufExtractor


def run_system_application(
        executable_cores, app_id, transceiver, provenance_file_path,
        executable_finder, read_algorithm_iobuf, check_for_success_function,
        cpu_end_states, needs_sync_barrier, filename_template,
        binaries_to_track=None, progress_bar=None, logger=None):
    """ Executes the given _system_ application. \
        Used for on-chip expanders, compressors, etc.

    :param ~spinnman.model.ExecutableTargets executable_cores:
        the cores to run the executable on
    :param int app_id: the app-id for the executable
    :param ~spinnman.transceiver.Transceiver transceiver: the SpiNNMan instance
    :param str provenance_file_path:
        the path for where provenance data is stored
    :param ExecutableFinder executable_finder: finder for executable paths
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
    :param ~logging.Logger logger:
        If provided and IOBUF is extracted, will be used to log errors and
        warnings
    :type progress_bar: ~spinn_utilities.progress_bar.ProgressBar or None
    :raise SpinnmanException:
        If one should arise from the underlying SpiNNMan calls
    """

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
    try:
        transceiver.wait_for_cores_to_be_in_state(
            check_targets.all_core_subsets, app_id, cpu_end_states,
            progress_bar=progress_bar)
        if progress_bar is not None:
            progress_bar.end()
        succeeded = True
    except SpinnmanException as ex:
        # Delay the exception until iobuf is ready
        error = ex

    if progress_bar is not None:
        progress_bar.end()

    # Check if any cores have not completed successfully
    if succeeded and check_for_success_function:
        succeeded = check_for_success_function(executable_cores, transceiver)

    # if doing iobuf or on failure (succeeded is None is not failure)
    if read_algorithm_iobuf or not succeeded:
        _report_iobuf_messages(
            transceiver, executable_cores, executable_finder, logger,
            filename_template, provenance_file_path)

    # stop anything that's associated with the compressor binary
    transceiver.stop_application(app_id)
    transceiver.app_id_tracker.free_id(app_id)

    if error is not None:
        raise error  # pylint: disable=raising-bad-type


def _report_iobuf_messages(
        txrx, cores, exe_finder, logger, filename_template, directory):
    """
    :param Transceiver txrx:
    :param ~spinnman.model.ExecutableTargets cores:
    :param ExecutableFinder exe_finder:
    :param ~logging.Logger logger:
    :param str filename_template:
    :param str directory:
    """
    # Import in this function to prevent circular import issue
    iobuf_reader = IOBufExtractor(
        txrx, cores, exe_finder, app_provenance_file_path=directory,
        system_provenance_file_path=directory,
        filename_template=filename_template, suppress_progress=False)
    error_entries, warn_entries = iobuf_reader.extract_iobuf()
    if logger is not None:
        for entry in warn_entries:
            logger.warn(entry)
        for entry in error_entries:
            logger.error(entry)
