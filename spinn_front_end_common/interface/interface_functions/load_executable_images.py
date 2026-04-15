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
from typing import Callable
import logging
from spinn_utilities.progress_bar import ProgressBar
from spinn_utilities.log import FormatAdapter
from spinnman.messages.scp.enums import Signal
from spinnman.model import ExecutableTargets
from spinnman.model.enums import CPUState, ExecutableType
from spinnman.exceptions import (
    SpiNNManCoresNotInStateException, SpinnmanException)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.helpful_functions import (
    flood_fill_binary_to_spinnaker)
from spinn_front_end_common.utilities.emergency_recovery import (
    emergency_recover_states_from_failure)
from spinn_front_end_common.utilities.iobuf_extractor import IOBufExtractor

# 10 seconds is lots of time to wait for the application to become ready!
_APP_READY_TIMEOUT = 10.0
_running_state = frozenset([CPUState.RUNNING])
logger = FormatAdapter(logging.getLogger(__name__))


def load_app_images() -> None:
    """
    Go through the executable targets and load each binary to everywhere
    and then send a start request to the cores that actually use it.
    """
    _load_images(lambda ty: ty is not ExecutableType.SYSTEM,
                 "Loading executables onto the machine")


def load_sys_images() -> None:
    """
    Go through the executable targets and load each binary to everywhere
    and then send a start request to the cores that actually use it.
    """
    _load_images(lambda ty: ty is ExecutableType.SYSTEM,
                 "Loading system executables onto the machine")
    try:
        cores = filter_targets(lambda ty: ty is ExecutableType.SYSTEM)
        FecDataView.get_transceiver().wait_for_cores_to_be_in_state(
            cores.all_core_subsets, FecDataView.get_app_id(),
            _running_state, timeout=10)
    except SpiNNManCoresNotInStateException as e:
        emergency_recover_states_from_failure()
        raise e


def _load_images(filter_predicate: Callable[[ExecutableType], bool],
                 label: str) -> None:
    """
    :param callable(ExecutableType,bool) filter_predicate:
    :param str label
    """
    # Compute what work is to be done here
    cores = filter_targets(filter_predicate)

    try:
        with ProgressBar(cores.total_processors + 1, label) as progress:
            for binary in cores.binaries:
                progress.update(flood_fill_binary_to_spinnaker(binary))

            _start_simulation(cores, FecDataView.get_app_id())
            progress.update()
    except Exception as e:
        try:

            transceiver = FecDataView.get_transceiver()
            unsuccessful_cores = transceiver.get_cpu_infos(
                    cores.all_core_subsets, [CPUState.READY], False)
            logger.error(unsuccessful_cores.get_status_string())
            IOBufExtractor().extract_iobuf()
            transceiver.stop_application(FecDataView.get_app_id())
        except SpinnmanException:
            # Ignore this, this was just an attempt at recovery
            pass
        raise e


def filter_targets(
        filter_predicate: Callable[[ExecutableType], bool]
        ) -> ExecutableTargets:
    """
    Creates a subset of all executable targets that pass the filter.

    :param filter_predicate: method to use as the filter
    :returns:Executable target with only those that pass the filter check
    """
    cores = ExecutableTargets()
    targets = FecDataView.get_executable_targets()
    for exe_type in targets.executable_types_in_binary_set():
        if filter_predicate(exe_type):
            for aplx in targets.get_binaries_of_executable_type(exe_type):
                cores.add_subsets(
                    aplx, targets.get_cores_for_binary(aplx), exe_type)
    return cores


def _start_simulation(cores: ExecutableTargets, app_id: int) -> None:
    """
    :param cores: Possible subset of all ExecutableTargets to start
    :param app_id:
    """
    txrx = FecDataView.get_transceiver()
    txrx.wait_for_cores_to_be_in_state(
        cores.all_core_subsets, app_id, frozenset([CPUState.READY]),
        timeout=_APP_READY_TIMEOUT)
    txrx.send_signal(app_id, Signal.START)
