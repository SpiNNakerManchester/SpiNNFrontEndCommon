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

from spinn_utilities.log import FormatAdapter
from spinn_machine import CoreSubsets
from spinnman.model import ExecutableTargets, CPUInfos
from spinnman.model.enums import CPUState
from spinn_front_end_common.data import FecDataView
from .chip_provenance_updater import (
    chip_provenance_updater, send_chip_update_provenance_and_exit)
from .iobuf_extractor import IOBufExtractor

logger = FormatAdapter(logging.getLogger(__name__))


def _emergency_state_check():
    """
    :param int app_id: the app id
    """
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
        machine = txrx.get_machine_details()
        infos = CPUInfos()
        errors = list()
        for chip in machine.chips:
            for p in chip.processors:
                try:
                    info = txrx.get_cpu_information_from_core(
                        chip.x, chip.y, p)
                    if info.state in (
                            CPUState.RUN_TIME_EXCEPTION, CPUState.WATCHDOG):
                        infos.add_processor(chip.x, chip.y, p, info)
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


def _emergency_iobuf_extract(executable_targets=None):
    """
    :param executable_targets:
        The specific targets to extract, or `None` for all
    :type executable_targets: ExecutableTargets or None
    """
    # pylint: disable=protected-access
    extractor = IOBufExtractor(
        executable_targets,
        recovery_mode=True, filename_template="emergency_iobuf_{}_{}_{}.txt")
    extractor.extract_iobuf()


def _emergency_exit():
    """ Tries to get the cores to exit
    """
    # pylint: disable=broad-except
    all_core_subsets = CoreSubsets()
    for place in FecDataView.iterate_placemements():
        all_core_subsets.add_processor(place.x, place.y, place.p)
    try:
        chip_provenance_updater(all_core_subsets)
    except Exception:
        logger.error("Could not exit - going to individual chips")
        errors = list()
        txrx = FecDataView.get_transceiver()
        for chip_subset in all_core_subsets:
            try:
                chip_subsets = CoreSubsets([chip_subset])
                running_cores = txrx.get_cpu_infos(
                    chip_subsets, CPUState.RUNNING, include=True)
                for (c_x, c_y, proc) in running_cores.keys():
                    send_chip_update_provenance_and_exit(txrx, c_x, c_y, proc)
                # Don't even bother to check; with luck this happens and all
                # is well, but at this point we can't do much more than send
                # the request and hope!
            except Exception:
                errors.append((chip_subset.x, chip_subset.y))
        if len(errors) > 10:
            logger.error(f"Could not stop cores on {len(errors)} chips")
        elif errors:
            logger.error(f"Could not stop cores on {errors}")


def emergency_recover_state_from_failure(vertex, placement):
    """
    Used to get at least *some* information out of a core when something
    goes badly wrong. Not a replacement for what abstract spinnaker base does.

    :param ~spinnman.transceiver.Transceiver txrx: The transceiver.
    :param AbstractHasAssociatedBinary vertex:
        The vertex to retrieve the IOBUF from if it is suspected as being dead
    :param ~pacman.model.placements.Placement placement:
        Where the vertex is located.
    """
    # pylint: disable=protected-access
    _emergency_state_check()
    target = ExecutableTargets()
    path = FecDataView.get_executable_path(vertex.get_binary_file_name())
    target.add_processor(
        path, placement.x, placement.y, placement.p,
        vertex.get_binary_start_type())
    _emergency_iobuf_extract(target)


def emergency_recover_states_from_failure():
    """
    Used to get at least *some* information out of a core when something
    goes badly wrong. Not a replacement for what abstract spinnaker base does.

    :param ~spinnman.model.ExecutableTargets executable_targets:
        The what/where mapping
    """
    _emergency_state_check()
    _emergency_exit()
    _emergency_iobuf_extract()
