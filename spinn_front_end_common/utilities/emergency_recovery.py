# Copyright (c) 2017-2020 The University of Manchester
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
import logging

from spinn_utilities.log import FormatAdapter
from spinnman.model import ExecutableTargets, CPUInfos
from spinnman.model.enums import CPUState
from .iobuf_extractor import IOBufExtractor
from .globals_variables import get_simulator

logger = FormatAdapter(logging.getLogger(__name__))


def _emergency_state_check(txrx, app_id):
    """
    :param ~.Transceiver txrx:
    :param int app_id:
    """
    # pylint: disable=broad-except
    try:
        rte_count = txrx.get_core_state_count(
            app_id, CPUState.RUN_TIME_EXCEPTION)
        watchdog_count = txrx.get_core_state_count(app_id, CPUState.WATCHDOG)
        if rte_count or watchdog_count:
            logger.warning(
                "unexpected core states (rte={}, wdog={})",
                txrx.get_cores_in_state(None, CPUState.RUN_TIME_EXCEPTION),
                txrx.get_cores_in_state(None, CPUState.WATCHDOG))
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
        logger.warning(txrx.get_core_status_string(infos))
        logger.warning("Could not read information from cores {}".format(
            errors))


# TRICKY POINT: Have to delay the import to here because of import circularity
def _emergency_iobuf_extract(txrx, executable_targets):
    """
    :param ~.Transceiver txrx:
    :param ExecutableTargets executable_targets:
    """
    # pylint: disable=protected-access
    sim = get_simulator()
    extractor = IOBufExtractor(
        txrx, executable_targets, sim._executable_finder,
        sim._app_provenance_file_path, sim._system_provenance_file_path,
        recovery_mode=True, filename_template="emergency_iobuf_{}_{}_{}.txt")
    extractor.extract_iobuf()


def emergency_recover_state_from_failure(txrx, app_id, vertex, placement):
    """ Used to get at least *some* information out of a core when something\
        goes badly wrong. Not a replacement for what abstract spinnaker base\
        does.

    :param ~spinnman.transceiver.Transceiver txrx: The transceiver.
    :param int app_id: The ID of the application.
    :param AbstractHasAssociatedBinary vertex:
        The vertex to retrieve the IOBUF from if it is suspected as being dead
    :param ~pacman.model.placements.Placement placement:
        Where the vertex is located.
    """
    # pylint: disable=protected-access
    _emergency_state_check(txrx, app_id)
    target = ExecutableTargets()
    path = get_simulator()._executable_finder.get_executable_path(
        vertex.get_binary_file_name())
    target.add_processor(
        path, placement.x, placement.y, placement.p,
        vertex.get_binary_start_type())
    _emergency_iobuf_extract(txrx, target)


def emergency_recover_states_from_failure(txrx, app_id, executable_targets):
    """ Used to get at least *some* information out of a core when something\
        goes badly wrong. Not a replacement for what abstract spinnaker base\
        does.

    :param ~spinnman.transceiver.Transceiver txrx: The transceiver.
    :param int app_id: The ID of the application.
    :param ~spinnman.model.ExecutableTargets executable_targets:
        The what/where mapping
    """
    _emergency_state_check(txrx, app_id)
    _emergency_iobuf_extract(txrx, executable_targets)
