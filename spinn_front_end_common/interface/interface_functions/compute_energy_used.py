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

import itertools
from spinn_utilities.config_holder import (get_config_int, get_config_str)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance import (
    GlobalProvenance, ProvenanceReader, TimerCategory, TimerWork)
from spinn_front_end_common.utilities.utility_objs import PowerUsed
from spinn_front_end_common.utility_models import (
    ChipPowerMonitorMachineVertex)

#: milliseconds per second
_MS_PER_SECOND = 1000.0

#: given from Indar's measurements
MILLIWATTS_PER_FPGA = 0.000584635

#: stated in papers (SpiNNaker: A 1-W 18 core system-on-Chip for
#: Massively-Parallel Neural Network Simulation)
JOULES_PER_SPIKE = 0.000000000800

#: stated in papers (SpiNNaker: A 1-W 18 core system-on-Chip for
#: Massively-Parallel Neural Network Simulation)
MILLIWATTS_PER_IDLE_CHIP = 0.000360

#: stated in papers (SpiNNaker: A 1-W 18 core system-on-Chip for
#: Massively-Parallel Neural Network Simulation)
MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD = (0.001 - MILLIWATTS_PER_IDLE_CHIP)

#: measured from the real power meter and timing between
#: the photos for a days powered off
MILLIWATTS_FOR_FRAME_IDLE_COST = 0.117

#: measured from the loading of the column and extrapolated
MILLIWATTS_PER_FRAME_ACTIVE_COST = 0.154163558

#: measured from the real power meter and timing between the photos
#: for a day powered off
MILLIWATTS_FOR_BOXED_48_CHIP_FRAME_IDLE_COST = 0.0045833333

# TODO needs filling in
MILLIWATTS_PER_UNBOXED_48_CHIP_FRAME_IDLE_COST = 0.01666667

# TODO verify this is correct when doing multiboard comms
N_MONITORS_ACTIVE_DURING_COMMS = 2


def compute_energy_used():
    """
    This algorithm does the actual work of computing energy used by a
    simulation (or other application) running on SpiNNaker.

    :rtype: PowerUsed
    """
    machine = FecDataView.get_machine()
    with GlobalProvenance() as db:
        dsg_time = db.get_category_timer_sum(TimerCategory.DATA_GENERATION)
        execute_time = db.get_category_timer_sum(TimerCategory.RUN_LOOP)
        # NOTE: this extraction time is part of the execution time; it does not
        # refer to the time taken in e.g. pop.get_data() or projection.get()
        extraction_time = db.get_timer_sum_by_work(TimerWork.EXTRACT_DATA)
        load_time = db.get_category_timer_sum(TimerCategory.LOADING)
        mapping_time = db.get_category_timer_sum(TimerCategory.MAPPING)
    # TODO get_machine not include here
    power_used = PowerUsed()

    power_used.num_chips = machine.n_chips
    # One extra per chip for SCAMP
    power_used.num_cores = FecDataView.get_n_placements() + machine.n_chips
    power_used.exec_time_secs = execute_time / _MS_PER_SECOND
    power_used.loading_time_secs = load_time / _MS_PER_SECOND
    # extraction_time could be None if nothing is set to be recorded
    total_extraction_time = 0
    if extraction_time is not None:
        total_extraction_time += extraction_time
    power_used.saving_time_secs = total_extraction_time / _MS_PER_SECOND
    power_used.data_gen_time_secs = dsg_time / _MS_PER_SECOND
    power_used.mapping_time_secs = mapping_time / _MS_PER_SECOND

    runtime_total_ms = (
            FecDataView.get_current_run_timesteps() *
            FecDataView.get_time_scale_factor())
    # TODO: extraction time as currently defined is part of execution time,
    #       so for now don't add it on, but revisit this in the future
    total_booted_time = execute_time + load_time
    _compute_energy_consumption(
         machine, dsg_time, load_time, mapping_time, total_booted_time,
         runtime_total_ms, power_used)

    return power_used


def _compute_energy_consumption(
        machine, dsg_time, load_time, mapping_time, total_booted_time,
        runtime_total_ms, power_used):
    """
    :param ~.Machine machine:
    :param float dsg_time:
    :param float load_time:
    :param float mapping_time:
    :param float total_booted_time:
    :param float runtime_total_ms:
    :param PowerUsed power_used:
    """
    # figure active chips
    monitor_placements = __find_monitor_placements()

    # figure out packet cost
    _router_packet_energy(power_used)

    # figure FPGA cost over all booted and during runtime cost
    _calculate_fpga_energy(
        machine, total_booted_time, runtime_total_ms, power_used)

    # figure how many frames are using, as this is a constant cost of
    # routers, cooling etc
    power_used.num_frames = _calculate_n_frames(machine)

    # figure load time cost
    power_used.loading_joules = _calculate_loading_energy(
        machine, load_time, len(monitor_placements), power_used.num_frames)

    # figure the down time idle cost for mapping
    power_used.mapping_joules = _calculate_power_down_energy(
        mapping_time, machine, power_used.num_frames)

    # figure the down time idle cost for DSG
    power_used.data_gen_joules = _calculate_power_down_energy(
        dsg_time, machine, power_used.num_frames)

    # figure extraction time cost
    power_used.saving_joules = _calculate_data_extraction_energy(
        machine, len(monitor_placements), power_used.num_frames)

    # figure out active chips cost
    power_used.chip_energy_joules = sum(
        _calculate_chips_active_energy(
            placement, runtime_total_ms, power_used)
        for placement in monitor_placements)

    # figure out cooling/internet router idle cost during runtime
    power_used.baseline_joules = (
        runtime_total_ms * power_used.num_frames *
        MILLIWATTS_FOR_FRAME_IDLE_COST)


def __find_monitor_placements():
    return [placement
            for placement in FecDataView.iterate_placements_by_vertex_type(
                ChipPowerMonitorMachineVertex)]


_COST_PER_TYPE = {
    "Local_Multicast_Packets": JOULES_PER_SPIKE,
    "External_Multicast_Packets": JOULES_PER_SPIKE,
    "Reinjected": JOULES_PER_SPIKE,
    "Local_P2P_Packets": JOULES_PER_SPIKE * 2,
    "External_P2P_Packets": JOULES_PER_SPIKE * 2,
    "Local_NN_Packets": JOULES_PER_SPIKE,
    "External_NN_Packets": JOULES_PER_SPIKE,
    "Local_FR_Packets": JOULES_PER_SPIKE * 2,
    "External_FR_Packets": JOULES_PER_SPIKE * 2
}


def _router_packet_energy(power_used):
    """
    :param PowerUsed power_used:
    """
    energy_cost = 0.0
    with ProvenanceReader() as db:
        for name, cost in _COST_PER_TYPE.items():
            data = db.get_router_by_chip(name)
            for (x, y, value) in data:
                this_cost = value * cost
                energy_cost += this_cost
                if this_cost:
                    power_used.add_router_active_energy(x, y, this_cost)

    power_used.packet_joules = energy_cost


def _calculate_chips_active_energy(placement, runtime_total_ms, power_used):
    """
    Figure out the chip active cost during simulation.

    :param ~.Placement placement: placement
    :param float runtime_total_ms:
    :param PowerUsed power_used:
    :return: energy cost
    """
    # locate chip power monitor
    chip_power_monitor = placement.vertex

    # get recordings from the chip power monitor
    recorded_measurements = chip_power_monitor.get_recorded_data(
        placement=placement)

    # deduce time in milliseconds per recording element
    n_samples_per_recording = get_config_int(
        "EnergyMonitor", "n_samples_per_recording_entry")
    time_for_recorded_sample = (
        chip_power_monitor.sampling_frequency *
        n_samples_per_recording) / 1000
    cores_power_cost = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    # accumulate costs
    for recorded_measurement in recorded_measurements:
        for core in range(0, 18):
            cores_power_cost[core] += (
                recorded_measurement[core] * time_for_recorded_sample *
                MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD / 18)

    # detailed report print out
    for core in range(0, 18):
        power_used.add_core_active_energy(
            placement.x, placement.y, core, cores_power_cost[core])

    # TAKE INTO ACCOUNT IDLE COST
    idle_cost = runtime_total_ms * MILLIWATTS_PER_IDLE_CHIP
    return sum(cores_power_cost) + idle_cost


def _calculate_fpga_energy(
        machine, total_runtime, runtime_total_ms, power_used):
    """
    :param ~.Machine machine:
    :param float total_runtime:
    :param float runtime_total_ms:
    :param PowerUsed power_used:
    """
    total_fpgas = 0
    # if not spalloc, then could be any type of board
    if (not get_config_str("Machine", "spalloc_server") and
            not get_config_str("Machine", "remote_spinnaker_url")):
        # if a spinn2 or spinn3 (4 chip boards) then they have no fpgas
        if machine.n_chips <= 4:
            return 0, 0

        # if the spinn4 or spinn5 board, need to verify if wrap-arounds
        # are there, if not then assume fpgas are turned off.

        # how many fpgas are active
        total_fpgas = __board_n_operational_fpgas(
            machine.ethernet_connected_chips[0])
        # active fpgas
        if total_fpgas == 0:
            return 0, 0
    else:  # spalloc machine, need to check each board
        for ethernet_connected_chip in machine.ethernet_connected_chips:
            total_fpgas += __board_n_operational_fpgas(
               ethernet_connected_chip)

    # Only need to update this here now that we've learned there are FPGAs
    # in use
    power_used.num_fpgas = total_fpgas
    power_usage_total = (
        total_runtime * MILLIWATTS_PER_FPGA * total_fpgas)
    power_usage_runtime = (
        runtime_total_ms * MILLIWATTS_PER_FPGA * total_fpgas)
    power_used.fpga_total_energy_joules = power_usage_total
    power_used.fpga_exec_energy_joules = power_usage_runtime


def __board_n_operational_fpgas(ethernet_chip):
    """
    Figures out how many FPGAs were switched on for a particular SpiNN-5 board.

    :param ~.Chip ethernet_chip: the Ethernet-enabled chip to look from
    :return: number of FPGAs on, on this board
    :rtype: int
    """
    # TODO: should be possible to get this info from Machine

    # As the Chips can be None use the machine call and not the View call
    machine = FecDataView.get_machine()

    # positions to check for active links
    left_chips = (
        machine.get_chip_at(ethernet_chip.x + dx, ethernet_chip.y + dy)
        for dx, dy in ((0, 0), (0, 1), (0, 2), (0, 3), (0, 4)))
    right_chips = (
        machine.get_chip_at(ethernet_chip.x + dx, ethernet_chip.y + dy)
        for dx, dy in ((7, 3), (7, 4), (7, 5), (7, 6), (7, 7)))
    top_chips = (
        machine.get_chip_at(ethernet_chip.x + dx, ethernet_chip.y + dy)
        for dx, dy in ((4, 7), (5, 7), (6, 7), (7, 7)))
    bottom_chips = (
        machine.get_chip_at(ethernet_chip.x + dx, ethernet_chip.y + dy)
        for dx, dy in ((0, 0), (1, 0), (2, 0), (3, 0), (4, 0)))
    top_left_chips = (
        machine.get_chip_at(ethernet_chip.x + dx, ethernet_chip.y + dy)
        for dx, dy in ((0, 3), (1, 4), (2, 5), (3, 6), (4, 7)))
    bottom_right_chips = (
        machine.get_chip_at(ethernet_chip.x + dx, ethernet_chip.y + dy)
        for dx, dy in ((0, 4), (1, 5), (2, 6), (3, 7)))

    # bottom left, bottom
    fpga_0 = __deduce_fpga(
        bottom_chips, bottom_right_chips, (5, 4), (0, 5))
    # left, and top right
    fpga_1 = __deduce_fpga(
        left_chips, top_left_chips, (3, 4), (3, 2))
    # top and right
    fpga_2 = __deduce_fpga(
        top_chips, right_chips, (2, 1), (0, 1))
    return fpga_0 + fpga_1 + fpga_2


def __deduce_fpga(chips_1, chips_2, links_1, links_2):
    """
    Figure out if each FPGA was on or not.

    :param iterable(~.Chip) chips_1: chips on an edge of the board
    :param iterable(~.Chip) chips_2: chips on an edge of the board
    :param iterable(int) links_1: which link IDs to check from chips_1
    :param iterable(int) links_2: which link IDs to check from chips_2
    :return: 0 if not on, 1 if on
    :rtype: int
    """
    for chip, link_id in itertools.product(chips_1, links_1):
        if chip and chip.router.get_link(link_id) is not None:
            return 1
    for chip, link_id in itertools.product(chips_2, links_2):
        if chip and chip.router.get_link(link_id) is not None:
            return 1
    return 0


def _calculate_loading_energy(machine, load_time_ms, n_monitors, n_frames):
    """
    :param ~.Machine machine:
    :param float load_time_ms: milliseconds
    :param int n_monitors
    :param int n_frames:
    :rtype: float
    """
    # find time in milliseconds
    with GlobalProvenance() as db:
        total_time_ms = db.get_timer_sum_by_category(TimerCategory.LOADING)

    # handle monitor core active cost

    # min between chips that are active and fixed monitor, as when 1
    # chip is used its one monitor, if more than 1 chip,
    # the ethernet connected chip and the monitor handling the read/write
    # this is checked by min
    n_monitors_active = min(N_MONITORS_ACTIVE_DURING_COMMS, n_monitors)
    energy_cost = (
        total_time_ms * n_monitors_active *
        MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD /
        machine.DEFAULT_MAX_CORES_PER_CHIP)

    # handle all idle cores
    energy_cost += _calculate_idle_cost(total_time_ms, machine)

    # handle time diff between load time and total load phase of ASB
    energy_cost += (
        (total_time_ms - load_time_ms) *
        machine.n_chips * MILLIWATTS_PER_IDLE_CHIP)

    # handle active routers etc
    active_router_cost = (
        load_time_ms * n_frames * MILLIWATTS_PER_FRAME_ACTIVE_COST)

    # accumulate
    energy_cost += active_router_cost
    return energy_cost


def _calculate_data_extraction_energy(machine, n_monitors, n_frames):
    """
    Data extraction cost.

    :param ~.Machine machine: machine description
    :param int n_monitors:
    :param int n_frames:
    :return: cost of data extraction, in Joules
    :rtype: float
    """
    # find time
    # TODO is this what was desired
    total_time_ms = 0
    with GlobalProvenance() as db:
        buffer_time_ms = db.get_timer_sum_by_work(TimerWork.EXTRACT_DATA)

    energy_cost = 0
    # NOTE: Buffer time could be None if nothing was set to record
    if buffer_time_ms is not None:
        total_time_ms += buffer_time_ms

        # min between chips that are active and fixed monitor, as when 1
        # chip is used its one monitor, if more than 1 chip,
        # the ethernet connected chip and the monitor handling the read/write
        # this is checked by min
        energy_cost = (
            total_time_ms *
            min(N_MONITORS_ACTIVE_DURING_COMMS, n_monitors) *
            MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD /
            machine.DEFAULT_MAX_CORES_PER_CHIP)

        # add idle chip cost
        energy_cost += _calculate_idle_cost(total_time_ms, machine)

        # handle active routers etc
        energy_cost_of_active_router = (
            total_time_ms * n_frames * MILLIWATTS_PER_FRAME_ACTIVE_COST)
        energy_cost += energy_cost_of_active_router

    return energy_cost


def _calculate_idle_cost(time, machine):
    """
    Calculate energy used by being idle.

    :param float time: time machine was idle, in milliseconds
    :param ~.Machine machine: machine description
    :return: cost, in joules
    :rtype: float
    """
    return (time * machine.total_available_user_cores *
            MILLIWATTS_PER_IDLE_CHIP /
            machine.DEFAULT_MAX_CORES_PER_CHIP)


def _calculate_power_down_energy(time, machine, n_frames):
    """
    Calculate power down costs.

    :param float time: time powered down, in milliseconds
    :param ~.Machine machine:
    :param int n_frames: number of frames used by this machine
    :return: energy in joules
    :rtype: float
    """
    # if spalloc or hbp
    if FecDataView.has_allocation_controller():
        return time * n_frames * MILLIWATTS_FOR_FRAME_IDLE_COST
    # if 4 chip
    elif machine.n_chips <= 4:
        return machine.n_chips * time * MILLIWATTS_PER_IDLE_CHIP
    # if 48 chip
    else:
        return time * MILLIWATTS_FOR_BOXED_48_CHIP_FRAME_IDLE_COST


def _calculate_n_frames(machine):
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
