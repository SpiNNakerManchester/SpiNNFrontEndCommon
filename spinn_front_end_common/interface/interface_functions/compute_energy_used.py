# Copyright (c) 2017-2019 The University of Manchester
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

import itertools
from spinn_utilities.config_holder import (get_config_int, get_config_str)
from spinn_utilities.ordered_set import OrderedSet
from spinn_front_end_common.interface.provenance import (
    BUFFER, DATA_GENERATION, LOADING, MAPPING, ProvenanceReader, RUN_LOOP)
from spinn_front_end_common.utilities.utility_objs import PowerUsed
from spinn_front_end_common.utility_models import (
    ChipPowerMonitorMachineVertex)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.globals_variables import (
    time_scale_factor)

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
MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD = 0.001 - MILLIWATTS_PER_IDLE_CHIP

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


def compute_energy_used(
        placements, machine, version, runtime, buffer_manager,
        machine_allocation_controller=None):
    """ This algorithm does the actual work of computing energy used by a\
        simulation (or other application) running on SpiNNaker.

    :param ~pacman.model.placements.Placements placements:
    :param ~spinn_machine.Machine machine:
    :param int version:
        The version of the SpiNNaker boards in use.
    :param float runtime:
    :param BufferManager buffer_manager:
    :param float mapping_time:
        From simulator via :py:class:`~.FinaliseTimingData`.
    :param float load_time:
        From simulator via :py:class:`~.FinaliseTimingData`.
    :param float execute_time:
        From simulator via :py:class:`~.FinaliseTimingData`.
    :param float dsg_time:
        From simulator via :py:class:`~.FinaliseTimingData`.
    :param float extraction_time:
        From simulator via :py:class:`~.FinaliseTimingData`.
    :param spalloc_server: (optional)
    :type spalloc_server: str or None
    :param remote_spinnaker_url: (optional)
    :type remote_spinnaker_url: str or None
    :param MachineAllocationController machine_allocation_controller:
        (optional)
    :rtype: PowerUsed
    """
    # pylint: disable=too-many-arguments
    db = ProvenanceReader()
    dsg_time = db.get_category_timer_sum(DATA_GENERATION)
    execute_time = db.get_category_timer_sum(RUN_LOOP)
    # TODO some extraction time is also execute_time
    extraction_time = db.get_category_timer_sum(BUFFER)
    load_time = db.get_category_timer_sum(LOADING)
    mapping_time = db.get_category_timer_sum(MAPPING)
    # TODO get_machine not include here
    power_used = PowerUsed()

    power_used.num_chips = machine.n_chips
    # One extra per chip for SCAMP
    power_used.num_cores = placements.n_placements + machine.n_chips
    power_used.exec_time_secs = execute_time / _MS_PER_SECOND
    power_used.loading_time_secs = load_time / _MS_PER_SECOND
    power_used.saving_time_secs = extraction_time / _MS_PER_SECOND
    power_used.data_gen_time_secs = dsg_time / _MS_PER_SECOND
    power_used.mapping_time_secs = mapping_time / _MS_PER_SECOND

    runtime_total_ms = runtime * time_scale_factor()
    _compute_energy_consumption(
         placements, machine, version,
         dsg_time, buffer_manager, load_time,
         mapping_time, execute_time + load_time + extraction_time,
         machine_allocation_controller,
         runtime_total_ms, power_used)

    return power_used


def _compute_energy_consumption(
        placements, machine, version, dsg_time, buffer_manager,
        load_time, mapping_time, total_booted_time, job, runtime_total_ms,
        power_used):
    """
    :param ~.Placements placements:
    :param ~.Machine machine:
    :param int version:
    :param float dsg_time:
    :param BufferManager buffer_manager:
    :param float load_time:
    :param float mapping_time:
    :param float total_booted_time:
    :param MachineAllocationController job:
    :param float runtime_total_ms:
    :param PowerUsed power_used:
    """
    # figure active chips
    active_chips = __active_chips(machine, placements)

    # figure out packet cost
    _router_packet_energy(power_used)

    # figure FPGA cost over all booted and during runtime cost
    _calculate_fpga_energy(
        machine, version, total_booted_time,
        runtime_total_ms, power_used)

    # figure how many frames are using, as this is a constant cost of
    # routers, cooling etc
    power_used.num_frames = _calculate_n_frames(machine, job)

    # figure load time cost
    power_used.loading_joules = _calculate_loading_energy(
        machine, load_time, active_chips, power_used.num_frames)

    # figure the down time idle cost for mapping
    power_used.mapping_joules = _calculate_power_down_energy(
        mapping_time, machine, job, version, power_used.num_frames)

    # figure the down time idle cost for DSG
    power_used.data_gen_joules = _calculate_power_down_energy(
        dsg_time, machine, job, version, power_used.num_frames)

    # figure extraction time cost
    power_used.saving_joules = _calculate_data_extraction_energy(
        machine, active_chips, power_used.num_frames)

    # figure out active chips cost
    power_used.chip_energy_joules = sum(
        _calculate_chips_active_energy(
            chip, placements, buffer_manager, runtime_total_ms, power_used)
        for chip in active_chips)

    # figure out cooling/internet router idle cost during runtime
    power_used.baseline_joules = (
        runtime_total_ms * power_used.num_frames *
        MILLIWATTS_FOR_FRAME_IDLE_COST)


def __active_chips(machine, placements):
    """
    :param ~.Machine machine:
    :param ~.Placements placements
    :rtype: set(~.Chip)
    """
    return OrderedSet(
        machine.get_chip_at(placement.x, placement.y)
        for placement in placements
        if isinstance(placement.vertex, ChipPowerMonitorMachineVertex))


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
    for name, cost in _COST_PER_TYPE.items():
        data = ProvenanceReader().get_router_by_chip(name)
        for (x, y, value) in data:
            this_cost = value * cost
            energy_cost += this_cost
            if this_cost:
                power_used.add_router_active_energy(x, y, this_cost)

    power_used.packet_joules = energy_cost


def _calculate_chips_active_energy(
        chip, placements, buffer_manager, runtime_total_ms, power_used):
    """ Figure out the chip active cost during simulation

    :param ~.Chip chip: the chip to consider
    :param ~.Placements placements: placements
    :param BufferManager buffer_manager: buffer manager
    :param float runtime_total_ms:
    :param PowerUsed power_used:
    :return: energy cost
    """
    # pylint: disable=too-many-arguments

    # locate chip power monitor
    chip_power_monitor = __get_chip_power_monitor(chip, placements)

    # get recordings from the chip power monitor
    recorded_measurements = chip_power_monitor.get_recorded_data(
        placement=placements.get_placement_of_vertex(chip_power_monitor),
        buffer_manager=buffer_manager)

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
            chip.x, chip.y, core, cores_power_cost[core])

    # TAKE INTO ACCOUNT IDLE COST
    idle_cost = runtime_total_ms * MILLIWATTS_PER_IDLE_CHIP
    return sum(cores_power_cost) + idle_cost


def __get_chip_power_monitor(chip, placements):
    """ Locate chip power monitor

    :param ~.Chip chip: the chip to consider
    :param ~.Placements placements: placements
    :return: the machine vertex coupled to the monitor
    :rtype: ChipPowerMonitorMachineVertex
    :raises Exception: if it can't find the monitor
    """
    # TODO this should be in the ChipPowerMonitor class
    # it is its responsibility, but needs the self-partitioning

    # start at top, as more likely it was placed on the top
    for processor in chip.processors:
        if placements.is_processor_occupied(
                chip.x, chip.y, processor.processor_id):
            # check if vertex is a chip power monitor
            vertex = placements.get_vertex_on_processor(
                chip.x, chip.y, processor.processor_id)
            if isinstance(vertex, ChipPowerMonitorMachineVertex):
                return vertex

    raise Exception("expected to find a chip power monitor!")


def _calculate_fpga_energy(
        machine, version, total_runtime, runtime_total_ms,
        power_used):
    """
    :param ~.Machine machine:
    :param int version:
    :param float total_runtime:
    :param float runtime_total_ms:
    :param PowerUsed power_used:
    """
    # pylint: disable=too-many-arguments

    total_fpgas = 0
    # if not spalloc, then could be any type of board
    if (not get_config_str("Machine", "spalloc_server") and
            not get_config_str("Machine", "remote_spinnaker_url")):
        # if a spinn2 or spinn3 (4 chip boards) then they have no fpgas
        if int(version) in (2, 3):
            return 0, 0
        elif int(version) not in (4, 5):
            # No idea what we've got here!
            raise ConfigurationException(
                "Do not know what the FPGA setup is for this version of "
                "SpiNNaker machine.")

        # if the spinn4 or spinn5 board, need to verify if wrap-arounds
        # are there, if not then assume fpgas are turned off.

        # how many fpgas are active
        total_fpgas = __board_n_operational_fpgas(
            machine, machine.ethernet_connected_chips[0])
        # active fpgas
        if total_fpgas == 0:
            return 0, 0
    else:  # spalloc machine, need to check each board
        for ethernet_connected_chip in machine.ethernet_connected_chips:
            total_fpgas += __board_n_operational_fpgas(
                machine, ethernet_connected_chip)

    # Only need to update this here now that we've learned there are FPGAs
    # in use
    power_used.num_fpgas = total_fpgas
    power_usage_total = (
        total_runtime * MILLIWATTS_PER_FPGA * total_fpgas)
    power_usage_runtime = (
        runtime_total_ms * MILLIWATTS_PER_FPGA * total_fpgas)
    power_used.fpga_total_energy_joules = power_usage_total
    power_used.fpga_exec_energy_joules = power_usage_runtime


def __board_n_operational_fpgas(machine, ethernet_chip):
    """ Figures out how many FPGAs were switched on for a particular \
        SpiNN-5 board.

    :param ~.Machine machine: SpiNNaker machine
    :param ~.Chip ethernet_chip: the ethernet chip to look from
    :return: number of FPGAs on, on this board
    """
    # pylint: disable=too-many-locals

    # TODO: should be possible to get this info from Machine

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
    """ Figure out if each FPGA was on or not

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


def _calculate_loading_energy(machine, load_time_ms, active_chips, n_frames):
    """
    :param ~.Machine machine:
    :param float load_time_ms: milliseconds
    :param list active_chips:
    :param int n_frames:
    :rtype: float
    """
    # pylint: disable=too-many-arguments

    # find time in milliseconds
    reader = ProvenanceReader()
    total_time_ms = reader.get_timer_sum_by_category("loading")

    # handle monitor core active cost

    # min between chips that are active and fixed monitor, as when 1
    # chip is used its one monitor, if more than 1 chip,
    # the ethernet connected chip and the monitor handling the read/write
    # this is checked by min
    n_monitors_active = min(
        N_MONITORS_ACTIVE_DURING_COMMS, len(active_chips))
    energy_cost = (
        total_time_ms * n_monitors_active *
        MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD /
        machine.DEFAULT_MAX_CORES_PER_CHIP)

    # handle all idle cores
    energy_cost += _calculate_idle_cost(total_time_ms, machine)

    # handle time diff between load time and total load phase of ASB
    energy_cost += (
        (load_time_ms - total_time_ms) *
        machine.n_chips * MILLIWATTS_PER_IDLE_CHIP)

    # handle active routers etc
    active_router_cost = (
        load_time_ms * n_frames * MILLIWATTS_PER_FRAME_ACTIVE_COST)

    # accumulate
    energy_cost += active_router_cost
    return energy_cost


def _calculate_data_extraction_energy(machine, active_chips, n_frames):
    """ Data extraction cost

    :param ~.Machine machine: machine description
    :param list active_chips:
    :param int n_frames:
    :return: cost of data extraction in Joules
    :rtype: float
    """
    # pylint: disable=too-many-arguments

    # find time
    # TODO is this what was desired
    total_time_ms = ProvenanceReader().get_category_timer_sum(BUFFER)

    # min between chips that are active and fixed monitor, as when 1
    # chip is used its one monitor, if more than 1 chip,
    # the ethernet connected chip and the monitor handling the read/write
    # this is checked by min
    energy_cost = (
        total_time_ms *
        min(N_MONITORS_ACTIVE_DURING_COMMS, len(active_chips)) *
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
    """ Calculate energy used by being idle.

    :param float time: time machine was idle, in milliseconds
    :param ~.Machine machine: machine description
    :return: cost in joules
    :rtype: float
    """
    return (time * machine.total_available_user_cores *
            MILLIWATTS_PER_IDLE_CHIP /
            machine.DEFAULT_MAX_CORES_PER_CHIP)


def _calculate_power_down_energy(time, machine, job, version, n_frames):
    """ Calculate power down costs

    :param float time: time powered down, in milliseconds
    :param ~.Machine machine:
    :param AbstractMachineAllocationController job:
        the spalloc job object
    :param int version:
    :param int n_frames: number of frames used by this machine
    :return: energy in joules
    :rtype: float
    """
    # pylint: disable=too-many-arguments

    # if spalloc or hbp
    if job is not None:
        return time * n_frames * MILLIWATTS_FOR_FRAME_IDLE_COST
    # if 48 chip
    elif version == 5 or version == 4:
        return time * MILLIWATTS_FOR_BOXED_48_CHIP_FRAME_IDLE_COST
    # if 4 chip
    elif version == 3 or version == 2:
        return machine.n_chips * time * MILLIWATTS_PER_IDLE_CHIP
    # boom
    else:
        raise ConfigurationException("don't know what to do here")


def _calculate_n_frames(machine, job):
    """ Figures out how many frames are being used in this setup.\
        A key of cabinet,frame will be used to identify unique frame.

    :param ~.Machine machine: the machine object
    :param AbstractMachineAllocationController job:
        the spalloc job object
    :return: number of frames
    :rtype: int
    """

    # if not spalloc, then could be any type of board, but unknown cooling
    if job is None:
        return 0

    # if using spalloc in some form
    cabinet_frame = set()
    for ethernet_connected_chip in machine.ethernet_connected_chips:
        cabinet, frame, _ = job.where_is_machine(
            ethernet_connected_chip.x, ethernet_connected_chip.y)
        cabinet_frame.add((cabinet, frame))
    return len(cabinet_frame)
