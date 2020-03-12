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
import re
from spinn_front_end_common.utilities.utility_objs import PowerUsed
from spinn_front_end_common.utility_models import (
    ChipPowerMonitorMachineVertex)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.helpful_functions import (
    convert_time_diff_to_total_milliseconds)

#: milliseconds per second
_MS_PER_SECOND = 1000.0


class ComputeEnergyUsed(object):
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

    #: converter between joules to kilowatt hours
    JOULES_TO_KILOWATT_HOURS = 3600000

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

    __slots__ = []

    def __call__(
            self, placements, machine, version, spalloc_server,
            remote_spinnaker_url, time_scale_factor,
            pacman_provenance, router_provenance, runtime,
            buffer_manager, mapping_time, load_time, execute_time, dsg_time,
            extraction_time, machine_allocation_controller=None):
        """
        :param ~.Placements placements:
        :param ~.Machine machine:
        :param int version:
        :param spalloc_server:
        :param str remote_spinnaker_url:
        :param int time_scale_factor:
        :param pacman_provenance:
        :param router_provenance:
        :param runtime:
        :param buffer_manager:
        :param mapping_time:
        :param load_time:
        :param execute_time:
        :param dsg_time:
        :param extraction_time:
        :param machine_allocation_controller:
        :rtype: PowerUsed
        """
        # pylint: disable=too-many-arguments

        power_used = PowerUsed()
        power_used.num_chips = machine.n_chips
        # One extra per chip for SCAMP
        power_used.num_cores = placements.n_placements + machine.n_chips
        power_used.exec_time_secs = execute_time / _MS_PER_SECOND
        power_used.loading_time_secs = load_time / _MS_PER_SECOND
        power_used.saving_time_secs = extraction_time / _MS_PER_SECOND
        power_used.data_gen_time_secs = dsg_time / _MS_PER_SECOND
        power_used.mapping_time_secs = mapping_time / _MS_PER_SECOND

        self._compute_energy_consumption(
             placements, machine, version, spalloc_server,
             remote_spinnaker_url, pacman_provenance, router_provenance,
             dsg_time, buffer_manager, load_time, mapping_time,
             execute_time + load_time + extraction_time,
             machine_allocation_controller,
             runtime * time_scale_factor, power_used)

        return power_used

    def _compute_energy_consumption(
            self, placements, machine, version, spalloc_server,
            remote_spinnaker_url, pacman_provenance, router_provenance,
            dsg_time, buffer_manager, load_time, mapping_time,
            total_booted_time, job, runtime_total_ms, power_used):
        """
        :rtype: tuple(float,float,float,float,float,float)
        """
        # figure active chips
        active_chips = set()
        for placement in placements:
            if not isinstance(placement.vertex, ChipPowerMonitorMachineVertex):
                active_chips.add(machine.get_chip_at(placement.x, placement.y))

        # figure out packet cost
        self._router_packet_energy(router_provenance, power_used)

        # figure FPGA cost over all booted and during runtime cost
        fpga_cost_total, fpga_cost_runtime = self._calculate_fpga_energy(
            machine, version, spalloc_server, remote_spinnaker_url,
            total_booted_time, runtime_total_ms, power_used)
        power_used.fpga_total_energy_joules = fpga_cost_total
        power_used.fpga_exec_energy_joules = fpga_cost_runtime

        # figure how many frames are using, as this is a constant cost of
        # routers, cooling etc
        n_frames = self._calculate_n_frames(machine, job)

        # figure load time cost
        power_used.loading_joules = self._calculate_loading_energy(
            pacman_provenance, machine, load_time, active_chips, n_frames)

        # figure the down time idle cost for mapping
        power_used.mapping_joules = self._calculate_power_down_energy(
            mapping_time, machine, job, version, n_frames)

        # figure the down time idle cost for DSG
        power_used.data_gen_joules = self._calculate_power_down_energy(
            dsg_time, machine, job, version, n_frames)

        # figure extraction time cost
        power_used.saving_joules = self._calculate_data_extraction_energy(
            pacman_provenance, machine, active_chips, n_frames)

        # figure out active chips cost
        power_used.chip_energy_joules = sum(
            self._calculate_chips_active_energy(
                chip, placements, buffer_manager, runtime_total_ms, power_used)
            for chip in active_chips)

        # figure out cooling/internet router idle cost during runtime
        power_used.baseline_joules = (
            runtime_total_ms * n_frames * self.MILLIWATTS_FOR_FRAME_IDLE_COST)

    _PER_CHIP_NAMES = set((
        "expected_routers", "unexpected_routers"))
    _MULTICAST_COUNTER_NAMES = set((
        "Local_Multicast_Packets", "External_Multicast_Packets", "Reinjected"))
    _PEER_TO_PEER_COUNTER_NAMES = set((
        "Local_P2P_Packets", "External_P2P_Packets"))
    _NEAREST_NEIGHBOUR_COUNTER_NAMES = set((
        "Local_NN_Packets", "External_NN_Packets"))
    _FIXED_ROUTE_COUNTER_NAMES = set((
        "Local_FR_Packets", "External_FR_Packets"))

    def _router_packet_energy(self, router_provenance, power_used):
        """
        :param PowerUsed power_used:
        """
        energy_cost = 0.0
        for element in router_provenance:
            # only process per chip counters, not summary counters.
            if element.names[1] not in self._PER_CHIP_NAMES:
                continue

            # process MC packets
            if element.names[3] in self._MULTICAST_COUNTER_NAMES:
                this_cost = float(element.value) * self.JOULES_PER_SPIKE

            # process p2p packets
            elif element.names[3] in self._PEER_TO_PEER_COUNTER_NAMES:
                this_cost = float(element.value) * self.JOULES_PER_SPIKE * 2

            # process NN packets
            elif element.names[3] in self._NEAREST_NEIGHBOUR_COUNTER_NAMES:
                this_cost = float(element.value) * self.JOULES_PER_SPIKE

            # process FR packets
            elif element.names[3] in self._FIXED_ROUTE_COUNTER_NAMES:
                this_cost = float(element.value) * self.JOULES_PER_SPIKE * 2

            else:
                # ???
                this_cost = 0.0

            energy_cost += this_cost

            # If we can record this against a particular chip, also do so
            m = re.match(r"router_at_chip_(\d+)_(\d+)", element.names[2])
            if m and this_cost:
                x = int(m.group[1])
                y = int(m.group[2])
                power_used.add_router_active_energy(x, y, this_cost)

        power_used.packet_joules = energy_cost

    def _calculate_chips_active_energy(
            self, chip, placements, buffer_manager, runtime_total_ms,
            power_used):
        """ Figure out the chip active cost during simulation

        :param ~.Chip chip: the chip to consider
        :param ~.Placements placements: placements
        :param BufferManager buffer_manager: buffer manager
        :param PowerUsed power_used:
        :return: energy cost
        """
        # pylint: disable=too-many-arguments

        # locate chip power monitor
        chip_power_monitor = self._get_chip_power_monitor(chip, placements)

        # get recordings from the chip power monitor
        recorded_measurements = chip_power_monitor.get_recorded_data(
            placement=placements.get_placement_of_vertex(chip_power_monitor),
            buffer_manager=buffer_manager)

        # deduce time in milliseconds per recording element
        time_for_recorded_sample = (
            chip_power_monitor.sampling_frequency *
            chip_power_monitor.n_samples_per_recording) / 1000
        cores_power_cost = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        # accumulate costs
        for recorded_measurement in recorded_measurements:
            for core in range(0, 18):
                cores_power_cost[core] += (
                    recorded_measurement[core] * time_for_recorded_sample *
                    self.MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD / 18)

        # detailed report print out
        for core in range(0, 18):
            power_used.add_core_active_energy(
                chip.x, chip.y, core, cores_power_cost[core])

        # TAKE INTO ACCOUNT IDLE COST
        idle_cost = runtime_total_ms * self.MILLIWATTS_PER_IDLE_CHIP
        return sum(cores_power_cost) + idle_cost

    def _get_chip_power_monitor(self, chip, placements):
        """ Locate chip power monitor

        :param ~.Chip chip: the chip to consider
        :param ~.Placements placements: placements
        :return: the machine vertex coupled to the monitor
        :rtype: ChipPowerMonitorMachineVertex
        :raises Exception: if it can't find the monitor
        """
        # start at top, as more likely it was placed on the top
        for processor_id in range(chip.n_processors):
            if placements.is_processor_occupied(chip.x, chip.y, processor_id):
                # check if vertex is a chip power monitor
                vertex = placements.get_vertex_on_processor(
                    chip.x, chip.y, processor_id)
                if isinstance(vertex, ChipPowerMonitorMachineVertex):
                    return vertex

        raise Exception("expected to find a chip power monitor!")

    def _calculate_fpga_energy(
            self, machine, version, spalloc_server, remote_spinnaker_url,
            total_runtime, runtime_total_ms, power_used):
        """
        :param ~.Machine machine:
        :param PowerUsed power_used:
        """
        # pylint: disable=too-many-arguments

        total_fpgas = 0
        # if not spalloc, then could be any type of board
        if spalloc_server is None and remote_spinnaker_url is None:
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
            total_fpgas = self._board_n_operational_fpgas(
                machine, machine.ethernet_connected_chips[0])
            # active fpgas
            if total_fpgas == 0:
                return 0, 0
        else:  # spalloc machine, need to check each board
            for ethernet_connected_chip in machine.ethernet_connected_chips:
                total_fpgas += self._board_n_operational_fpgas(
                    machine, ethernet_connected_chip)

        # Only need to update this here now that we've learned there are FPGAs
        # in use
        power_used.num_fpgas = total_fpgas
        power_usage_total = (
            total_runtime * self.MILLIWATTS_PER_FPGA * total_fpgas)
        power_usage_runtime = (
            runtime_total_ms * self.MILLIWATTS_PER_FPGA * total_fpgas)
        power_used.fpga_total_energy_joules = power_usage_total
        power_used.fpga_exec_energy_joules = power_usage_runtime
        return power_usage_total, power_usage_runtime

    def _board_n_operational_fpgas(self, machine, ethernet_chip):
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
        fpga_0 = self.__deduce_fpga(
            bottom_chips, bottom_right_chips, (5, 4), (0, 5))
        # left, and top right
        fpga_1 = self.__deduce_fpga(
            left_chips, top_left_chips, (3, 4), (3, 2))
        # top and right
        fpga_2 = self.__deduce_fpga(
            top_chips, right_chips, (2, 1), (0, 1))
        return fpga_1 + fpga_0 + fpga_2

    @staticmethod
    def __deduce_fpga(chips_1, chips_2, links_1, links_2):
        """ Figure out if each FPGA was on or not

        :param iterable(~.Chip) chips_1: chips on an edge of the board
        :param iterable(~.Chip) chips_2: chips on an edge of the board
        :param iterable(int) links_1: which link IDs to check from chips_1
        :param iterable(int) links_2: which link IDs to check from chips_2
        :return: 0 if not on, 1 if on
        :rtype: int
        """
        # pylint: disable=too-many-arguments
        for chip, link_id in itertools.product(chips_1, links_1):
            if chip and chip.router.get_link(link_id) is not None:
                return 1
        for chip, link_id in itertools.product(chips_2, links_2):
            if chip and chip.router.get_link(link_id) is not None:
                return 1
        return 0

    def _calculate_loading_energy(
            self, pacman_provenance, machine, load_time_ms, active_chips,
            n_frames):
        """
        :param pacman_provenance:
        :param ~.Machine machine:
        :param float load_time_ms: milliseconds
        :param list active_chips:
        :param int n_frames:
        :rtype: float
        """
        # pylint: disable=too-many-arguments

        # find time in milliseconds
        total_time_ms = float(sum(
            convert_time_diff_to_total_milliseconds(element.value)
            for element in pacman_provenance
            if element.names[1] == "loading"))

        # handle monitor core active cost

        # min between chips that are active and fixed monitor, as when 1
        # chip is used its one monitor, if more than 1 chip,
        # the ethernet connected chip and the monitor handling the read/write
        # this is checked by min
        n_monitors_active = min(
            self.N_MONITORS_ACTIVE_DURING_COMMS, len(active_chips))
        energy_cost = (
            total_time_ms * n_monitors_active *
            self.MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD /
            machine.DEFAULT_MAX_CORES_PER_CHIP)

        # handle all idle cores
        energy_cost += self._calculate_idle_cost(total_time_ms, machine)

        # handle time diff between load time and total load phase of ASB
        energy_cost += (
            (load_time_ms - total_time_ms) *
            machine.n_chips * self.MILLIWATTS_PER_IDLE_CHIP)

        # handle active routers etc
        active_router_cost = (
            load_time_ms * n_frames * self.MILLIWATTS_PER_FRAME_ACTIVE_COST)

        # accumulate
        energy_cost += active_router_cost
        return energy_cost

    def _calculate_data_extraction_energy(
            self, pacman_provenance, machine, active_chips, n_frames):
        """ Data extraction cost

        :param pacman_provenance: provenance items from the PACMAN set
        :param ~.Machine machine: machine description
        :param list active_chips:
        :param int n_frames:
        :return: cost of data extraction in Joules
        :rtype: float
        """
        # pylint: disable=too-many-arguments

        # find time
        total_time_ms = float(sum(
            convert_time_diff_to_total_milliseconds(element.value)
            for element in pacman_provenance
            if (element.names[1] == "Execution" and element.names[2] !=
                "run_time_of_FrontEndCommonApplicationRunner")))

        # min between chips that are active and fixed monitor, as when 1
        # chip is used its one monitor, if more than 1 chip,
        # the ethernet connected chip and the monitor handling the read/write
        # this is checked by min
        energy_cost = (
            total_time_ms *
            min(self.N_MONITORS_ACTIVE_DURING_COMMS, len(active_chips)) *
            self.MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD /
            machine.DEFAULT_MAX_CORES_PER_CHIP)

        # add idle chip cost
        energy_cost += self._calculate_idle_cost(total_time_ms, machine)

        # handle active routers etc
        energy_cost_of_active_router = (
            total_time_ms * n_frames * self.MILLIWATTS_PER_FRAME_ACTIVE_COST)
        energy_cost += energy_cost_of_active_router
        return energy_cost

    @classmethod
    def _calculate_idle_cost(cls, time, machine):
        """ Calculate energy used by being idle.

        :param float time: time machine was idle, in milliseconds
        :param ~.Machine machine: machine description
        :return: cost in joules
        :rtype: float
        """
        return (time * machine.total_available_user_cores *
                cls.MILLIWATTS_PER_IDLE_CHIP /
                machine.DEFAULT_MAX_CORES_PER_CHIP)

    @classmethod
    def _calculate_power_down_energy(cls, time, machine, job, version, n_frames):
        """ Calculate power down costs

        :param time: time powered down, in milliseconds
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
            return time * n_frames * cls.MILLIWATTS_FOR_FRAME_IDLE_COST
        # if 48 chip
        elif version == 5 or version == 4:
            return time * cls.MILLIWATTS_FOR_BOXED_48_CHIP_FRAME_IDLE_COST
        # if 4 chip
        elif version == 3 or version == 2:
            return machine.n_chips * time * cls.MILLIWATTS_PER_IDLE_CHIP
        # boom
        else:
            raise ConfigurationException("don't know what to do here")


    @staticmethod
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
