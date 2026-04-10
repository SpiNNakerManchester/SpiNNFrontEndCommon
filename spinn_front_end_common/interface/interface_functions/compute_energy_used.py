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
import logging
from typing import Final, Optional, cast, Dict, Tuple

import numpy

from spinn_utilities.config_holder import get_config_bool, get_config_int
from spinn_utilities.log import FormatAdapter

from spinn_machine import Machine
from spinn_machine.version.abstract_version import (
    AbstractVersion, RouterPackets)

from spinnman.model.enums.executable_type import ExecutableType

from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance import (
    GlobalProvenance, ProvenanceReader, TimerCategory, TimerWork)
from spinn_front_end_common.utilities.utility_objs import PowerUsed
from spinn_front_end_common.utility_models\
    .chip_power_monitor_machine_vertex import (
        RECORDING_CHANNEL, ChipPowerMonitorMachineVertex)
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import BufferDatabase
from spinn_front_end_common.abstract_models import AbstractHasAssociatedBinary

logger = FormatAdapter(logging.getLogger(__name__))

#: milliseconds per second
_MS_PER_SECOND: Final = 1000.0
#: microseconds per millisecond
_US_PER_MS: Final = 1000.0
#: microseconds per second
_US_PER_SECOND: Final = 1000000.0


def compute_energy_used(checkpoint: Optional[int] = None) -> PowerUsed:
    """
    This algorithm does the actual work of computing energy used by a
    simulation (or other application) running on SpiNNaker.

    :param checkpoint: the time at which to compute execution energy up to
    :returns: Summary object of power used
    """
    # Get data from provenance
    with GlobalProvenance() as db:
        total_on_ms = db.get_machine_on_by_reset()
        mapping_ms = db.get_timer_sum_by_category_and_reset(
            TimerCategory.MAPPING)
        loading_ms = db.get_timer_sum_by_category_and_reset(
            TimerCategory.LOADING)

        # Separate out processes that are part of the others but that happen
        # on the machine, so we can account for active machine, not idle
        data_loading_ms = db.get_timer_sum_by_work_and_reset(
            TimerWork.LOADING_DATA)
        if get_config_bool("Machine", "enable_advanced_monitor_support"):
            data_extraction_ms = db.get_timer_sum_by_work_and_reset(
                TimerWork.EXTRACT_DATA)
        else:
            data_extraction_ms = 0
        expansion_ms = db.get_timer_sum_by_work_and_reset(
            TimerWork.SYNAPSE)

    if checkpoint is not None:
        execute_on_machine_ms = checkpoint
    else:
        timesteps = FecDataView.get_current_run_timesteps()
        if timesteps is None:
            raise ValueError(
                "Cannot compute energy without knowing the end time")
        ts_factor = FecDataView.get_time_scale_factor()
        timestep = FecDataView.get_simulation_time_step_ms()
        execute_on_machine_ms = int(round(timesteps * ts_factor) * timestep)

    machine = FecDataView.get_machine()
    version = FecDataView.get_machine_version()

    active_cores: Dict[Tuple[int, int], int] = defaultdict(int)
    power_cores: Dict[Tuple[int, int], int] = {}
    n_active_cores = 0
    for pl in FecDataView.iterate_placemements():
        if not isinstance(pl.vertex, AbstractHasAssociatedBinary):
            continue
        vertex: AbstractHasAssociatedBinary = cast(
            AbstractHasAssociatedBinary, pl.vertex)
        if vertex.get_binary_start_type() != ExecutableType.SYSTEM:
            if isinstance(vertex, ChipPowerMonitorMachineVertex):
                power_cores[(pl.x, pl.y)] = pl.p
            else:
                active_cores[(pl.x, pl.y)] += 1
                n_active_cores += 1
    n_active_chips = len(active_cores)

    n_monitors_all = (version.n_scamp_cores
                      + FecDataView.get_all_monitor_cores())
    n_extra_monitors_ethernet = (FecDataView.get_ethernet_monitor_cores() -
                                 FecDataView.get_all_monitor_cores())

    if get_config_bool("Reports", "write_energy_report"):
        # Don't count the cost of the EnergyMonitor cores
        n_monitors_all -= - 1
        sum_run_active_time = _extract_cores_active_time(
            checkpoint, active_cores, power_cores, version)
    else:
        sum_run_active_time = _assume_core_always_active(
            active_cores, execute_on_machine_ms)

    total_monitors = (
            machine.n_chips * n_monitors_all +
            machine.n_ethernet_connected_chips * n_extra_monitors_ethernet)
    sum_load_active_time = data_loading_ms / _MS_PER_SECOND * total_monitors
    sum_extraction_active_time = data_extraction_ms / _MS_PER_SECOND * total_monitors

    run_router_packets = _extract_router_packets("Run", version)
    load_router_packets = _extract_router_packets("Load", version)
    extraction_router_packets = _extract_router_packets("Extract", version)

    return compute_energy_over_time(
        total_on_ms, mapping_ms, loading_ms,
        data_loading_ms, expansion_ms, data_extraction_ms,
        execute_on_machine_ms, version, n_active_chips,
        n_active_cores, sum_load_active_time, sum_extraction_active_time,
        sum_run_active_time, load_router_packets, extraction_router_packets,
        run_router_packets)


def _calculate_n_frames(machine: Machine) -> int:
    """
    Figures out how many frames are being used in this setup.
    A key of cabinet,frame will be used to identify unique frame.

    :param machine: the machine object
    :return: number of frames
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
    packets_per_chip: RouterPackets = defaultdict(dict)
    with ProvenanceReader() as db:
        for name in version.get_router_report_packet_types():
            for (x, y, value) in db.get_router_by_chip(f"{prefix}{name}"):
                packets_per_chip[x, y][name] = value
    return packets_per_chip


def _extract_cores_active_time(
        checkpoint: Optional[int], active_cores: Dict[Tuple[int, int], int],
        power_cores: Dict[Tuple[int, int], int],
        version: AbstractVersion) -> float:
    sampling_frequency = get_config_int("EnergyMonitor", "sampling_frequency")

    sum_activity: float = 0
    with BufferDatabase() as buff_db:
        for (x, y), n_cores in active_cores.items():
            # Find the core that was used on this chip for power monitoring
            p = power_cores[(x, y)]
            # Get time per sample in seconds (frequency in microseconds)
            time_for_recorded_sample_s = sampling_frequency / _US_PER_SECOND
            data, _missing = buff_db.get_recording(x, y, p, RECORDING_CHANNEL)
            results = numpy.frombuffer(data, dtype=numpy.uint32).reshape(
                -1, version.max_cores_per_chip + 1)
            # Get record times in milliseconds (frequency in microseconds)
            record_times = results[:, 0] * sampling_frequency / _US_PER_MS
            # The remaining columns are the counts of active / inactive at
            # each sample point
            activity = results[:, 1:].astype(numpy.float64)
            # Set the activity of *this* core to 0, as we don't want to
            # measure that!
            physical_core = FecDataView.get_physical_core_id((x, y), p)
            activity[:, physical_core] = 0
            # Convert to actual active time, assuming the core is fully active
            # or fully inactive between samples
            activity_times = activity * time_for_recorded_sample_s
            # If checkpoint is specified, filter the times
            if checkpoint is not None:
                activity_times = activity_times[record_times < checkpoint]
            sum_activity += activity_times.sum()
    return sum_activity


def _assume_core_always_active(
        active_cores: Dict[Tuple[int, int], int],
        execute_on_machine_ms: float) -> float:
    """
    As there are no power monitors assume cores always active

    """
    logger.warning(
        "Energy monitoring cores not enabled, assuming all cores were"
        " active for whole run time.  To get a better energy estimate,"
        " set write_energy_report=True in the [Reports] section of the"
        " configuration file")
    sum_activity: float = 0
    for n_cores in active_cores.values():
        sum_activity += (execute_on_machine_ms * n_cores) / _MS_PER_SECOND
    return sum_activity


def compute_energy_over_time(
        total_on_ms: float, mapping_ms: float, loading_ms: float,
        data_loading_ms: float, expansion_ms: float,
        data_extraction_ms: float, execute_on_machine_ms: float,
        version: AbstractVersion,
        n_active_chips: int, n_active_cores: int,
        sum_load_active_time: float,
        sum_extraction_active_time: float,
        sum_run_active_time: float,
        load_router_packets: RouterPackets,
        extraction_router_packets: RouterPackets,
        run_router_packets: RouterPackets) -> PowerUsed:
    """
    Compute the energy used by a simulation running on SpiNNaker.

    :param total_on_ms: Total time the machine was on for thios reset
    :param mapping_ms: time spent mapping to the machine
    :param loading_ms:
        time spent loading the simulation onto the passive machine
        Includes the data_loading_ms and expansion_ms
    :param data_loading_ms:
        time spent loading data onto the machine actively using the machine to
        load the data
    :param expansion_ms: time spent expanding the data on the machine
    :param data_extraction_ms:
        time spent extracting data from the machine actively using the machine
        to extract the data
    :param execute_on_machine_ms:
        time spent executing the simulation on the machine actively using it
    :param version: the version of the machine
    :param n_active_chips: number of chips active in simulation
    :param n_active_cores: number of cores actively used by the simulation
    :param sum_load_active_time:
        sum of times that cores where active during loading
    :param sum_extraction_chip_active_time:
        sum of time that cores where active during extraction
    :param sum_run_active_time:
        sum of times that cores where active during running
    :param load_router_packets:
        packets sent by the machine during loading
    :param extraction_router_packets:
        packets sent by the machine during extraction
    :param run_router_packets:
        packets sent by the machine during running
    :returns: Summary object of power used
    """
    machine = FecDataView.get_machine()
    n_boards = machine.n_ethernet_connected_chips
    n_chips = machine.n_chips
    n_cores = FecDataView.get_n_placements()
    n_frames = _calculate_n_frames(machine)

    # Time and energy spent on the host machine, with the machine (at least
    # theoretically) running, doing general software tasks that we don't want
    # to put in other categories.
    other_time_ms = (total_on_ms - mapping_ms - loading_ms -
                     data_extraction_ms - execute_on_machine_ms)
    other_time_s = other_time_ms / _MS_PER_SECOND
    other_energy_j = version.get_idle_energy(
        other_time_s, n_frames, n_boards, n_chips)

    # Time and energy mapping to the machine
    mapping_time_s = mapping_ms / _MS_PER_SECOND
    mapping_energy_j = version.get_idle_energy(
        mapping_time_s, n_frames, n_boards, n_chips)

    # Time and energy spent loading data onto the machine
    loading_active_ms = data_loading_ms + expansion_ms
    loading_active_s = loading_active_ms / _MS_PER_SECOND
    loading_time_s = loading_ms / _MS_PER_SECOND
    loading_idle_s = loading_time_s - loading_active_s
    loading_energy_j = version.get_idle_energy(
        loading_idle_s,  n_frames, n_boards, n_chips)
    loading_energy_j += version.get_active_energy(
        loading_active_s, n_frames, n_boards,
        n_chips, sum_load_active_time, load_router_packets)

    # Time and energy spent extracting data from the machine
    saving_time_s = data_extraction_ms / _MS_PER_SECOND
    saving_energy_j = version.get_active_energy(
        saving_time_s, n_frames, n_boards, n_chips,
        sum_extraction_active_time, extraction_router_packets)

    # Time and energy spent running the simulation on the machine
    exec_time_s = execute_on_machine_ms / _MS_PER_SECOND
    exec_energy_j = version.get_active_energy(
        exec_time_s, n_frames, n_boards, n_chips,
        sum_run_active_time, run_router_packets)
    exec_energy_cores_j = version.get_active_energy(
        exec_time_s, 0, 0, n_active_chips, sum_run_active_time,
        run_router_packets)
    exec_energy_boards_j = version.get_active_energy(
        exec_time_s, 0, n_boards, n_chips, sum_run_active_time,
        run_router_packets)

    return PowerUsed(
        n_chips, n_active_chips, n_cores, n_active_cores, n_boards, n_frames,
        exec_time_s, mapping_time_s, loading_time_s, saving_time_s,
        other_time_s, exec_energy_j, exec_energy_cores_j, exec_energy_boards_j,
        mapping_energy_j, loading_energy_j, saving_energy_j, other_energy_j)
