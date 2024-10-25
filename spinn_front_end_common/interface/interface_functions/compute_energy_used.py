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

from collections import defaultdict
from typing import Final, List, Optional
from spinn_utilities.config_holder import get_config_bool
from spinn_machine import Machine
from spinn_machine.version.abstract_version import (
    AbstractVersion, ChipActiveTime, RouterPackets)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance import (
    GlobalProvenance, ProvenanceReader, TimerCategory, TimerWork)
from spinn_front_end_common.utilities.utility_objs import PowerUsed
from spinn_front_end_common.interface.interface_functions\
    .load_data_specification import load_using_advanced_monitors
from spinn_front_end_common.utility_models\
    .chip_power_monitor_machine_vertex import PROVENANCE_TIME_KEY

#: milliseconds per second
_MS_PER_SECOND: Final = 1000.0


def compute_energy_used(checkpoint: Optional[int] = None) -> PowerUsed:
    """
    This algorithm does the actual work of computing energy used by a
    simulation (or other application) running on SpiNNaker.

    :rtype: PowerUsed
    """
    # Get data from provenance
    with GlobalProvenance() as db:
        waiting_ms = db.get_category_timer_sum(TimerCategory.WAITING)
        setup_ms = db.get_timer_sum_by_category(TimerCategory.SETTING_UP)
        get_machine_ms = db.get_timer_sum_by_category(
            TimerCategory.GET_MACHINE)

        mapping_ms = db.get_timer_sum_by_category(TimerCategory.MAPPING)
        loading_ms = db.get_timer_sum_by_category(TimerCategory.LOADING)

        run_other_ms = db.get_timer_sum_by_category(TimerCategory.RUN_OTHER)
        run_loop_ms = db.get_timer_sum_by_category(TimerCategory.RUN_LOOP)
        resetting_ms = db.get_timer_sum_by_category(TimerCategory.RESETTING)

        shutting_down_ms = db.get_timer_sum_by_category(
            TimerCategory.SHUTTING_DOWN)

        # Separate out processes that are part of the others but that happen
        # on the machine, so we can account for active machine, not idle
        data_loading_ms = 0
        if load_using_advanced_monitors():
            data_loading_ms = db.get_timer_sum_by_work(TimerWork.LOADING_DATA)
            loading_ms -= data_loading_ms
        data_extraction_ms = 0
        if get_config_bool("Machine", "enable_advanced_monitor_support"):
            data_extraction_ms = db.get_timer_sum_by_work(
                TimerWork.EXTRACT_DATA)
            run_loop_ms -= data_extraction_ms
        expansion_ms = db.get_timer_sum_by_work(TimerWork.SYNAPSE)
        loading_ms -= expansion_ms

    if checkpoint is not None:
        execute_on_machine_ms = checkpoint
    else:
        timesteps = FecDataView.get_current_run_timesteps()
        if timesteps is not None:
            ts_factor = FecDataView.get_time_scale_factor()
            execute_on_machine_ms = timesteps * ts_factor
        else:
            execute_on_machine_ms = FecDataView.get_measured_run_time_ms()

    run_loop_ms -= execute_on_machine_ms

    machine = FecDataView.get_machine()
    version = FecDataView.get_machine_version()
    n_boards = len(machine.ethernet_connected_chips)
    n_chips = machine.n_chips
    n_cores = FecDataView.get_n_placements()
    n_frames = _calculate_n_frames(machine)

    run_chip_active_time = _extract_cores_active_time(checkpoint)
    load_chip_active_time = _make_extra_monitor_core_use(
        data_loading_ms, machine, version.n_scamp_cores + 2,
        version.n_scamp_cores + 1)
    extraction_chip_active_time = _make_extra_monitor_core_use(
        data_extraction_ms, machine, version.n_scamp_cores + 2,
        version.n_scamp_cores + 1)

    run_router_packets = _extract_router_packets("Run")
    load_router_packets = _extract_router_packets("Load")
    extraction_router_packets = _extract_router_packets("Extract")

    # TODO get_machine not include here
    return compute_energy_over_time(
        waiting_ms, setup_ms, get_machine_ms, mapping_ms, loading_ms,
        data_loading_ms, expansion_ms, data_extraction_ms, run_other_ms,
        run_loop_ms, execute_on_machine_ms, resetting_ms, shutting_down_ms,
        version, n_chips, n_boards, n_frames, n_cores, load_chip_active_time,
        extraction_chip_active_time, run_chip_active_time, load_router_packets,
        extraction_router_packets, run_router_packets)


def _calculate_n_frames(machine: Machine) -> int:
    """
    Figures out how many frames are being used in this setup.
    A key of cabinet,frame will be used to identify unique frame.

    :param ~.Machine machine: the machine object
    :return: number of frames
    :rtype: int
    """
    # if not spalloc, then could be any type of board, but unknown cooling
    if not FecDataView.has_allocation_controller():
        return 0

    # using spalloc in some form; how many unique frames?
    cabinet_frame = set()
    mac = FecDataView.get_allocation_controller()
    for ethernet_connected_chip in machine.ethernet_connected_chips:
        cabinet, frame, _ = mac.where_is_machine(
            ethernet_connected_chip.x, ethernet_connected_chip.y)
        cabinet_frame.add((cabinet, frame))
    return len(cabinet_frame)


def _extract_router_packets(
        prefix: str, version: AbstractVersion) -> RouterPackets:
    packets_per_chip = defaultdict(dict)
    with ProvenanceReader() as db:
        for name in version.get_router_report_packet_types():
            for (x, y, value) in db.get_router_by_chip(f"{prefix}{name}"):
                packets_per_chip[x, y][name] = value
    return packets_per_chip


def _extract_cores_active_time(
        checkpoint: Optional[int] = None) -> List[float]:
    key = PROVENANCE_TIME_KEY
    if checkpoint is not None:
        key = f"{PROVENANCE_TIME_KEY}_{checkpoint}"
    with ProvenanceReader() as db:
        data = {(x, y): value for (x, y, value) in db.get_monitor_by_chip(key)}
    return data


def _make_extra_monitor_core_use(
        time_ms: int, machine: Machine, extra_monitors_per_board: int,
        extra_monitors_per_chip: int) -> ChipActiveTime:
    time_s = time_ms / _MS_PER_SECOND
    core_use = defaultdict(list)
    for chip in machine.chips:
        n_monitors = extra_monitors_per_chip
        if chip.ip_address is not None:
            n_monitors += extra_monitors_per_board
        for core in range(n_monitors):
            core_use[chip.x, chip.y].append(time_s)
        for _ in range(core, chip.n_processors):
            core_use[chip.x, chip.y].append(0.0)
    return core_use


def compute_energy_over_time(
        waiting_ms: float, setup_ms: float, get_machine_ms: float,
        mapping_ms: float, loading_ms: float, data_loading_ms: float,
        expansion_ms: float, data_extraction_ms: float, run_other_ms: float,
        run_loop_ms: float, execute_on_machine_ms: float,
        resetting_ms: float, shutting_down_ms: float, version: AbstractVersion,
        n_chips: int, n_boards: int, n_frames: int, n_cores: int,
        load_chip_active_time: ChipActiveTime,
        extraction_chip_active_time: ChipActiveTime,
        run_chip_active_time: ChipActiveTime,
        load_router_packets: RouterPackets,
        extraction_router_packets: RouterPackets,
        run_router_packets: RouterPackets) -> PowerUsed:

    # Time and energy spent on the host machine, with the machine (at least
    # theoretically) running, doing general software tasks that we don't want
    # to put in other categories.
    other_time_s = (
        waiting_ms + setup_ms + get_machine_ms + shutting_down_ms +
        run_other_ms + run_loop_ms + resetting_ms) / _MS_PER_SECOND
    other_energy_j = version.get_idle_energy(
        other_time_s, n_frames, n_boards, n_chips)

    # Time and energy mapping to the machine
    mapping_time_s = mapping_ms / _MS_PER_SECOND
    mapping_energy_j = version.get_idle_energy(
        mapping_time_s, n_frames, n_boards, n_chips)

    # Time and energy spent loading data onto the machine
    loading_time_s = (
        loading_ms + data_loading_ms + expansion_ms) / _MS_PER_SECOND
    loading_energy_j = version.get_idle_energy(
        loading_ms / _MS_PER_SECOND, n_frames, n_boards, n_chips)
    loading_energy_j += version.get_active_energy(
        (data_loading_ms + expansion_ms) / _MS_PER_SECOND, n_frames, n_boards,
        n_chips, load_chip_active_time, load_router_packets)

    # Time and energy spent extracting data from the machine
    saving_time_s = data_extraction_ms / _MS_PER_SECOND
    saving_energy_j = version.get_active_energy(
        saving_time_s, n_frames, n_boards, n_chips,
        extraction_chip_active_time, extraction_router_packets)

    # Time and energy spent running the simulation on the machine
    exec_time_s = execute_on_machine_ms / _MS_PER_SECOND
    exec_energy_j = version.get_active_energy(
        exec_time_s, n_frames, n_boards, n_chips,
        run_chip_active_time, run_router_packets)

    return PowerUsed(
        n_chips, n_cores, n_boards, n_frames, exec_time_s, mapping_time_s,
        loading_time_s, saving_time_s, other_time_s, exec_energy_j,
        mapping_energy_j, loading_energy_j, saving_energy_j, other_energy_j)
