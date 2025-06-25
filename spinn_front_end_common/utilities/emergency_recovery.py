# Copyright (c) 2017 The University of Manchester
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
import logging
from typing import List, Optional, Tuple

from spinn_utilities.log import FormatAdapter

from spinnman.model import ExecutableTargets, CPUInfos
from spinnman.model.enums import CPUState

from pacman.model.placements import Placement

from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary
from spinn_front_end_common.data import FecDataView
from .iobuf_extractor import IOBufExtractor

logger = FormatAdapter(logging.getLogger(__name__))
_bad_states = frozenset((CPUState.RUN_TIME_EXCEPTION, CPUState.WATCHDOG))


def _emergency_state_check() -> None:
    # pylint: disable=broad-except
    try:
        app_id = FecDataView.get_app_id()
        txrx = FecDataView.get_transceiver()
        rte_count = txrx.get_core_state_count(
            app_id, CPUState.RUN_TIME_EXCEPTION)
        watchdog_count = txrx.get_core_state_count(app_id, CPUState.WATCHDOG)
        if rte_count or watchdog_count:
            states = txrx.get_cpu_infos(
                None, [CPUState.RUN_TIME_EXCEPTION, CPUState.WATCHDOG], True)
            logger.warning(
                "unexpected core states (rte={}, wdog={})",
                rte_count, watchdog_count)
            logger.warning(states.get_status_string())
    except Exception:
        logger.exception(
            "Could not read the status count - going to individual cores")
        machine = FecDataView.get_machine()
        infos = CPUInfos()
        errors: List[Tuple[int, int, int]] = list()
        for chip in machine.chips:
            for p in chip.all_processor_ids:
                try:
                    txrx.add_cpu_information_from_core(
                        infos, chip.x, chip.y, p, _bad_states)
                except Exception:
                    errors.append((chip.x, chip.y, p))
        if len(infos):
            logger.warning(infos.get_status_string())
        if len(errors) > 10:
            logger.warning(
                "Could not read information from {} cores", len(errors))
        else:
            logger.warning(
                "Could not read information from cores {}", errors)


def _emergency_iobuf_extract(
        executable_targets: Optional[ExecutableTargets] = None) -> None:
    """
    :param executable_targets:
        The specific targets to extract, or `None` for all
    """
    extractor = IOBufExtractor(
        executable_targets,
        recovery_mode=True, filename_template="emergency_iobuf_{}_{}_{}.txt")
    extractor.extract_iobuf()


def emergency_recover_state_from_failure(
        vertex: AbstractHasAssociatedBinary, placement: Placement) -> None:
    """
    Used to get at least *some* information out of a core when something
    goes badly wrong. Not a replacement for what abstract spinnaker base does.

    :param vertex:
        The vertex to retrieve the IOBUF from if it is suspected as being dead
    :param placement:
        Where the vertex is located.
    """
    _emergency_state_check()
    target = ExecutableTargets()
    path = FecDataView.get_executable_path(vertex.get_binary_file_name())
    target.add_processor(
        path, placement.x, placement.y, placement.p,
        vertex.get_binary_start_type())
    _emergency_iobuf_extract(target)


def emergency_recover_states_from_failure() -> None:
    """
    Used to get at least *some* information out of a core when something
    goes badly wrong. Not a replacement for what abstract spinnaker base does.
    """
    _emergency_state_check()
    _emergency_iobuf_extract()
