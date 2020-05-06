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

from spinn_front_end_common.interface.interface_functions import \
    ChipIOBufExtractor
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinnman.exceptions import SpinnmanException, SpinnmanTimeoutException
from spinnman.messages.scp.enums import Signal
from spinnman.model import ExecutableTargets


def run_system_application(
        executable_cores, app_id, transceiver, provenance_file_path,
        executable_finder, read_algorithm_iobuf, check_for_success_function,
        handle_failure_function, cpu_end_states, needs_sync_barrier,
        no_sync_changes, filename_template, binaries_to_track=None):
    """ executes the app

    :param executable_cores: the cores to run the executable on
    :param app_id: the appid for the executable
    :param transceiver: the SpiNNMan instance
    :param provenance_file_path: the path for where provenance data is\
    stored
    :param filename_template: the iobuf filename template.
    :param read_algorithm_iobuf: bool flag for report
    :param executable_finder: finder for executable paths
    :param check_for_success_function: function used to check success: \
    expects executable_cores, transceiver, as inputs
    :param handle_failure_function: function used to deal with failures\
    expects executable_cores, transceiver, provenance_file_path,\
    app_id, executable_finder as inputs
    :param needs_sync_barrier: bool flag for if needing sync barrier
    :param no_sync_changes: the number of times sync signal been sent
    :param binaries_to_track: a list of binary names to check for exit state.\
     Or None for all binaries
    :rtype: None
    """

    # load the executable
    transceiver.execute_application(executable_cores, app_id)

    if needs_sync_barrier:
        if no_sync_changes % 2 == 0:
            sync_signal = Signal.SYNC0
        else:
            sync_signal = Signal.SYNC1
        # when it falls out of the running, it'll be in a next sync \
        # state, thus update needed
        no_sync_changes += 1

        # fire all signals as required
        transceiver.send_signal(app_id, sync_signal)

    succeeded = False
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
    try:
        transceiver.wait_for_cores_to_be_in_state(
            check_targets.all_core_subsets, app_id, cpu_end_states)
        succeeded = True
    except (SpinnmanTimeoutException, SpinnmanException):
        handle_failure_function(executable_cores)
        succeeded = False

    # Check if any cores have not completed successfully
    if succeeded and check_for_success_function is not None:
        succeeded = check_for_success_function(executable_cores, transceiver)

    # if doing iobuf, read iobuf
    if read_algorithm_iobuf or not succeeded:
        iobuf_reader = ChipIOBufExtractor(filename_template=filename_template)
        iobuf_reader(
            transceiver, executable_cores, executable_finder,
            app_provenance_file_path=None,
            system_provenance_file_path=provenance_file_path)

    # stop anything that's associated with the compressor binary
    transceiver.stop_application(app_id)
    transceiver.app_id_tracker.free_id(app_id)
