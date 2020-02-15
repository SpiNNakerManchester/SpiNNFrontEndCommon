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

import logging
import os
from spinn_front_end_common.utility_models import ChipPowerMonitorMachineVertex
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.helpful_functions import (
    convert_time_diff_to_total_milliseconds)

logger = logging.getLogger(__name__)


class EnergyReport(object):
    """ Creates a report about the approximate total energy consumed by a\
        SpiNNaker job execution.
    """

    # given from indar measurements
    MILLIWATTS_PER_FPGA = 0.000584635

    # stated in papers (SpiNNaker: A 1-W 18 core system-on-Chip for
    # Massively-Parallel Neural Network Simulation)
    JOULES_PER_SPIKE = 0.000000000800

    # stated in papers (SpiNNaker: A 1-W 18 core system-on-Chip for
    # Massively-Parallel Neural Network Simulation)
    MILLIWATTS_PER_IDLE_CHIP = 0.000360

    # stated in papers (SpiNNaker: A 1-W 18 core system-on-Chip for
    # Massively-Parallel Neural Network Simulation)
    MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD = 0.001 - MILLIWATTS_PER_IDLE_CHIP

    # converter between joules to kilowatt hours
    JOULES_TO_KILOWATT_HOURS = 3600000

    # measured from the real power meter and timing between
    #  the photos for a days powered off
    MILLIWATTS_FOR_FRAME_IDLE_COST = 0.117

    # measured from the loading of the column and extrapolated
    MILLIWATTS_PER_FRAME_ACTIVE_COST = 0.154163558

    # measured from the real power meter and timing between the photos
    # for a day powered off
    MILLIWATTS_FOR_BOXED_48_CHIP_FRAME_IDLE_COST = 0.0045833333

    # TODO needs filling in
    MILLIWATTS_PER_UNBOXED_48_CHIP_FRAME_IDLE_COST = 0.01666667

    # TODO verify this is correct when doing multiboard comms
    N_MONITORS_ACTIVE_DURING_COMMS = 2

    # energy report file name
    ENERGY_DETAILED_FILENAME = "Detailed_energy_report.rpt"
    ENERGY_SUMMARY_FILENAME = "energy_summary_report.rpt"

    def __call__(
            self, placements, machine, report_default_directory, version,
            spalloc_server, remote_spinnaker_url, time_scale_factor,
            machine_time_step, pacman_provenance, router_provenance,
            machine_graph, runtime, buffer_manager, mapping_time, load_time,
            execute_time, dsg_time, extraction_time,
            machine_allocation_controller=None):
        """
        :param placements: the placements
        :param machine: the machine
        :param report_default_directory: location for reports
        :param version: version of machine
        :param spalloc_server: spalloc server IP
        :param remote_spinnaker_url: remote SpiNNaker URL
        :param time_scale_factor: the time scale factor
        :param machine_time_step: the machine time step
        :param pacman_provenance: the PACMAN provenance
        :param router_provenance: the router provenance
        :param machine_graph: the machine graph
        :param buffer_manager: the buffer manager
        :param mapping_time: time taken by the mapping process
        :param load_time: the time taken by the load process
        :param execute_time: the time taken by the execute time process
        :param dsg_time: the time taken by the DSG time
        :param extraction_time: the time taken by data extraction time
        :param machine_allocation_controller: \
            the machine controller for spalloc
        :rtype: None
        """
        # pylint: disable=too-many-arguments, too-many-locals
        if buffer_manager is None:
            logger.info("Skipping Energy report as no buffer_manager set")
            return

        # detailed report path
        detailed_report = os.path.join(
            report_default_directory, self.ENERGY_DETAILED_FILENAME)

        # summary report path
        summary_report = os.path.join(
            report_default_directory, self.ENERGY_SUMMARY_FILENAME)

        # overall time taken up
        total_time = (
            execute_time + load_time + extraction_time + dsg_time +
            mapping_time)

        # total time the machine was booted
        total_booted_time = execute_time + load_time + extraction_time

        # figure runtime in milliseconds with time scale factor
        runtime_total_ms = runtime * time_scale_factor

        # create detailed report
        with open(detailed_report, "w") as f:
            active_chip_cost, fpga_cost_total, fpga_cost_runtime, \
                packet_cost, mapping_cost, load_time_cost, \
                data_extraction_cost, dsg_cost, router_cooling_runtime_cost = \
                self._write_detailed_report(
                    placements, machine, version, spalloc_server,
                    remote_spinnaker_url, pacman_provenance, router_provenance,
                    dsg_time, buffer_manager, f, load_time, mapping_time,
                    total_booted_time, machine_allocation_controller,
                    runtime_total_ms)

        # create summary report
        with open(summary_report, "w") as f:
            self._write_summary_report(
                active_chip_cost, fpga_cost_total, fpga_cost_runtime,
                packet_cost, mapping_cost, load_time_cost,
                data_extraction_cost, runtime_total_ms, f,
                mapping_time, load_time, dsg_time, dsg_cost,
                extraction_time, total_time, total_booted_time,
                router_cooling_runtime_cost)

    @staticmethod
    def _write_summary_report(
            active_chip_cost, fpga_cost_total, fpga_cost_runtime, packet_cost,
            mapping_cost, load_time_cost, data_extraction_cost,
            runtime_total_ms, f, mapping_time, load_time,
            dsg_time, dsg_cost, extraction_time, total_time,
            total_booted_time, router_cooling_runtime_cost):
        """ Write summary file

        :param active_chip_cost: active chip cost
        :param fpga_cost_total: FPGA cost over all booted time
        :param fpga_cost_runtime: FPGA cost during runtime
        :param mapping_time: the time taken by the mapping process in ms
        :param mapping_cost: the energy used by the mapping process
        :param packet_cost: packet cost
        :param load_time_cost: load time cost
        :param data_extraction_cost: data extraction cost
        :param runtime_total_ms: \
            Runtime with time scale factor taken into account
        :param f: file writer
        :rtype: None
        """
        # pylint: disable=too-many-arguments, too-many-locals

        # total the energy costs
        total_joules = (
            active_chip_cost + fpga_cost_total + packet_cost + mapping_cost +
            load_time_cost + data_extraction_cost + dsg_cost +
            fpga_cost_runtime + router_cooling_runtime_cost)

        # deduce wattage from the runtime
        total_watts = total_joules / (total_time / 1000)

        # figure total kilowatt hour
        kilowatt_hours = total_joules / EnergyReport.JOULES_TO_KILOWATT_HOURS

        # write summary data
        f.write("Summary energy file\n-------------------\n\n")
        f.write(
            "Energy used by chips during runtime is {} Joules (over {} "
            "milliseconds)\n".format(active_chip_cost, runtime_total_ms))
        f.write(
            "Energy used by FPGAs is {} Joules (over the entire time the "
            "machine was booted {} milliseconds)\n".format(
                fpga_cost_total, total_booted_time))
        f.write(
            "Energy used by FPGAs is {} Joules (over the runtime period of "
            "{} milliseconds)\n".format(
                fpga_cost_runtime, runtime_total_ms))
        f.write(
            "Energy used by outside router / cooling during the runtime "
            "period is {} Joules\n".format(router_cooling_runtime_cost))
        f.write(
            "Energy used by packet transmissions is {} Joules (over {} "
            "milliseconds)\n".format(packet_cost, total_time))
        f.write(
            "Energy used during the mapping process is {} Joules (over {} "
            "milliseconds)\n".format(mapping_cost, mapping_time))
        f.write(
            "Energy used by the data generation process is {} Joules (over {} "
            "milliseconds)\n".format(dsg_cost, dsg_time))
        f.write(
            "Energy used during the loading process is {} Joules (over {} "
            "milliseconds)\n".format(load_time_cost, load_time))
        f.write(
            "Energy used during the data extraction process is {} Joules "
            "(over {} milliseconds\n".format(
                data_extraction_cost, extraction_time))
        f.write(
            "Total energy used by the simulation over {} milliseconds is:\n"
            "     {} Joules, or\n"
            "     {} estimated average Watts, or\n"
            "     {} kWh\n".format(
                total_time, total_joules, total_watts, kilowatt_hours))

    def _write_detailed_report(
            self, placements, machine, version, spalloc_server,
            remote_spinnaker_url,
            pacman_provenance, router_provenance, dsg_time,
            buffer_manager, f, load_time, mapping_time,
            total_booted_time, machine_allocation_controller,
            runtime_total_ms):
        """ Write detailed report and calculate costs

        :param placements: placements
        :param machine: machine representation
        :param version: machine version
        :param spalloc_server: spalloc server
        :param remote_spinnaker_url: remote SpiNNaker URL
        :param pacman_provenance: provenance generated by PACMAN
        :param router_provenance: provenance generated by the router
        :param buffer_manager: buffer manager
        :param f: file writer
        :param total_booted_time: time in milliseconds where machine is booted
        :param machine_allocation_controller:
        :param runtime_total_ms: \
            total runtime with time scale factor taken into account
        :return: machine_active_cost, machine_idle_chips_cost, \
            fpga_cost, packet_cost, load_time_cost, extraction_time_cost
        :rtype: tuple(float,float,float,float,float,float)
        """
        # pylint: disable=too-many-arguments, too-many-locals

        # write warning about accuracy etc
        self._write_warning(f)

        # figure active chips
        active_chips = set()
        for placement in placements:
            if not isinstance(placement.vertex, ChipPowerMonitorMachineVertex):
                active_chips.add(machine.get_chip_at(placement.x, placement.y))

        # figure out packet cost
        packet_cost = self._router_packet_cost(router_provenance, f)

        # figure FPGA cost over all booted and during runtime cost
        fpga_cost_total, fpga_cost_runtime = self._calculate_fpga_cost(
            machine, version, spalloc_server, remote_spinnaker_url,
            total_booted_time, f, runtime_total_ms)

        # figure how many frames are using, as this is a constant cost of
        # routers, cooling etc
        n_frames = self._calculate_n_frames(
            machine, machine_allocation_controller)

        # figure load time cost
        load_time_cost = self._calculate_load_time_cost(
            pacman_provenance, machine, f, load_time, active_chips, n_frames)

        # figure the down time idle cost for mapping
        mapping_cost = self._calculate_power_down_cost(
            mapping_time, machine, machine_allocation_controller, version,
            n_frames)

        # figure the down time idle cost for DSG
        dsg_cost = self._calculate_power_down_cost(
            dsg_time, machine, machine_allocation_controller, version,
            n_frames)

        # figure extraction time cost
        extraction_time_cost = self._calculate_data_extraction_time_cost(
            pacman_provenance, machine, f, active_chips, n_frames)

        # figure out active chips idle time
        machine_active_cost = 0.0
        for chip in active_chips:
            machine_active_cost += self._calculate_chips_active_cost(
                chip, placements, buffer_manager, f, runtime_total_ms)

        # figure out router idle cost during runtime
        router_cooling_runtime_cost = (
            runtime_total_ms * n_frames * self.MILLIWATTS_FOR_FRAME_IDLE_COST)

        # return all magic values
        return machine_active_cost, fpga_cost_total, fpga_cost_runtime, \
            packet_cost, mapping_cost, load_time_cost, extraction_time_cost, \
            dsg_cost, router_cooling_runtime_cost

    def _write_warning(self, f):
        """ Writes the warning about this being only an estimate

        :param f: the writer
        :rtype: None
        """

        f.write(
            "This report is based off energy estimates for individual "
            "components of the SpiNNaker machine. It is not meant to be "
            "completely accurate. But does use provenance data gathered from "
            "the machine to estimate the energy usage and therefore should "
            "be in the right ballpark.\n\n\n")
        f.write(
            "The energy components we use are as follows:\n\n"
            "The energy usage for a chip when all cores are 100% active for "
            "a millisecond is {} Joules.\n"
            "The energy usage for a chip when all cores are not active for a "
            "millisecond is {} Joules.\n"
            "The energy used by the machine for firing a packet is {} "
            "Joules.\n"
            "The energy used by each active FPGA per millisecond is {} "
            "Joules.\n\n\n"
            .format(
                self.MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD,
                self.MILLIWATTS_PER_IDLE_CHIP,
                self.JOULES_PER_SPIKE, self.MILLIWATTS_PER_FPGA))

    def _calculate_fpga_cost(
            self, machine, version, spalloc_server, remote_spinnaker_url,
            total_runtime, f, runtime_total_ms):
        """ FPGA cost calculation

        :param machine: machine representation
        :param version: machine version
        :param spalloc_server: spalloc server IP
        :param remote_spinnaker_url: remote SpiNNaker URL
        :param total_runtime: the runtime
        :param f: the file writer
        :param runtime_total_ms:
        :return: power usage of FPGAs
        :rtype: tuple(float,float)
        """
        # pylint: disable=too-many-arguments

        # if not spalloc, then could be any type of board
        if spalloc_server is None and remote_spinnaker_url is None:

            # if a spinn2 or spinn3 (4 chip boards) then they have no fpgas
            if int(version) in (2, 3):
                f.write(
                    "A SpiNN-{} board does not contain any FPGA's, and so "
                    "its energy cost is 0 \n".format(version))
                return 0, 0

            # if the spinn4 or spinn5 board, need to verify if wrap-arounds
            # are there, if not then assume fpgas are turned off.
            if int(version) in (4, 5):

                # how many fpgas are active
                n_operational_fpgas = self._board_n_operational_fpgas(
                    machine, machine.ethernet_connected_chips[0])

                # active fpgas
                if n_operational_fpgas > 0:
                    return self._print_out_fpga_cost(
                        total_runtime, n_operational_fpgas, f, version,
                        runtime_total_ms)
                # no active fpgas
                f.write(
                    "The FPGA's on the SpiNN-{} board are turned off and "
                    "therefore the energy used by the FPGA is 0\n".format(
                        version))
                return 0, 0

            # no idea where we are; version unrecognised
            raise ConfigurationException(
                "Do not know what the FPGA setup is for this version of "
                "SpiNNaker machine.")
        else:  # spalloc machine, need to check each board
            total_fpgas = 0
            for ethernet_connected_chip in machine.ethernet_connected_chips:
                total_fpgas += self._board_n_operational_fpgas(
                    machine, ethernet_connected_chip)
            return self._print_out_fpga_cost(
                total_runtime, total_fpgas, f, version, runtime_total_ms)

    def _print_out_fpga_cost(
            self, total_runtime, n_operational_fpgas, f, version,
            runtime_total_ms):
        """ Prints out to file and returns cost

        :param total_runtime: all runtime
        :param n_operational_fpgas: number of operational FPGAs
        :param f: file writer
        :param version: machine version
        :param runtime_total_ms: runtime in milliseconds
        :return: power usage
        """
        # pylint: disable=too-many-arguments
        power_usage_total = (
            total_runtime * self.MILLIWATTS_PER_FPGA * n_operational_fpgas)
        power_usage_runtime = (
            runtime_total_ms * self.MILLIWATTS_PER_FPGA * n_operational_fpgas)

        # print out as needed for spalloc and non-spalloc versions
        if version is None:
            f.write(
                "{} FPGAs on the Spalloc-ed boards are turned on and "
                "therefore the energy used by the FPGA during the entire time "
                "the machine was booted (which was {} ms) is {}. "
                "The usage during execution was {}".format(
                    n_operational_fpgas, total_runtime,
                    power_usage_total, power_usage_runtime))
        else:
            f.write(
                "{} FPGA's on the SpiNN-{} board are turned on and "
                "therefore the energy used by the FPGA during the entire time "
                "the machine was booted (which was {} ms) is {}. "
                "The usage during execution was {}".format(
                    n_operational_fpgas, version, total_runtime,
                    power_usage_total, power_usage_runtime))
        return power_usage_total, power_usage_runtime

    def _board_n_operational_fpgas(self, machine, ethernet_connected_chip):
        """ Figures out how many FPGAs were switched on.

        :param machine: SpiNNaker machine
        :param ethernet_connected_chip: the ethernet chip to look from
        :return: number of FPGAs on, on this board
        """
        # pylint: disable=too-many-locals

        # positions to check for active links
        left_additions = [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]
        right_additions = [(7, 3), (7, 4), (7, 5), (7, 6), (7, 7)]
        top_additions = [(4, 7), (5, 7), (6, 7), (7, 7)]
        bottom_additions = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]
        top_left_additions = [(0, 3), (1, 4), (2, 5), (3, 6), (4, 7)]
        bottom_right_additions = [(0, 4), (1, 5), (2, 6), (3, 7)]

        ethernet_chip_x = ethernet_connected_chip.x
        ethernet_chip_y = ethernet_connected_chip.y

        # bottom left, bottom
        fpga_0 = self._deduce_fpga(
            [bottom_additions, bottom_right_additions], [(5, 4), (0, 5)],
            ethernet_chip_x, ethernet_chip_y, machine)
        # left, and top right
        fpga_1 = self._deduce_fpga(
            [left_additions, top_left_additions], [(3, 4), (3, 2)],
            ethernet_chip_x, ethernet_chip_y, machine)
        # top and right
        fpga_2 = self._deduce_fpga(
            [top_additions, right_additions], [(2, 1), (0, 1)],
            ethernet_chip_x, ethernet_chip_y, machine)
        return fpga_1 + fpga_0 + fpga_2

    @staticmethod
    def _deduce_fpga(
            shifts, overall_link_ids, ethernet_chip_x, ethernet_chip_y,
            machine):
        """ Figure out if each FPGA was on or not

        :param shifts: shifts from ethernet to find a FPGA edge
        :type shifts: iterable(iterable(int))
        :param overall_link_ids: which link IDs to check
        :type overall_link_ids: iterable(iterable(int))
        :param ethernet_chip_x: ethernet chip x
        :param ethernet_chip_y: ethernet chip y
        :param machine: machine rep
        :return: 0 if not on, 1 if on
        """
        # pylint: disable=too-many-arguments
        for shift_group, link_ids in zip(shifts, overall_link_ids):
            for shift in shift_group:
                new_x = (ethernet_chip_x + shift[0]) % (machine.width)
                new_y = (ethernet_chip_y + shift[1]) % (machine.height)
                chip = machine.get_chip_at(new_x, new_y)
                if chip is not None:
                    for link_id in link_ids:
                        if chip.router.get_link(link_id) is not None:
                            return 1
        return 0

    def _get_chip_power_monitor(self, chip, placements):
        """ Locate chip power monitor

        :param chip: the chip to consider
        :param placements: placements
        :return: the machine vertex coupled to the monitor
        :raises Exception: if it can't find the monitor
        """
        # start at top, as more likely it was placed on the top
        for processor_id in range(17, -1, -1):
            processor = chip.get_processor_with_id(processor_id)
            if processor is not None and placements.is_processor_occupied(
                    chip.x, chip.y, processor_id):
                # check if vertex is a chip power monitor
                vertex = placements.get_vertex_on_processor(
                    chip.x, chip.y, processor_id)
                if isinstance(vertex, ChipPowerMonitorMachineVertex):
                    return vertex

        raise Exception("expected to find a chip power monitor!")

    def _calculate_chips_active_cost(
            self, chip, placements, buffer_manager, f, runtime_total_ms):
        """ Figure out the chip active cost during simulation

        :param chip: the chip to consider
        :param placements: placements
        :param buffer_manager: buffer manager
        :param f: file writer
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
            f.write(
                "processor {}:{}:{} used {} Joules of energy by being active "
                "during the execution of the simulation\n".format(
                    chip.x, chip.y, core, cores_power_cost[core]))

        total_energy_cost = 0.0
        for core_power_usage in cores_power_cost:
            total_energy_cost += core_power_usage

        # TAKE INTO ACCOUNT IDLE COST
        idle_cost = runtime_total_ms * self.MILLIWATTS_PER_IDLE_CHIP
        total_energy_cost += idle_cost

        f.write(
            "The machine used {} Joules of energy by being idle "
            "during the execution of the simulation".format(idle_cost))

        return total_energy_cost

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

    def _router_packet_cost(self, router_provenance, f):
        """ Figure out the packet cost; includes MC, P2P, FR, NN packets

        :param router_provenance: the provenance gained from the router
        :param f: file writer
        :rtype: energy usage value
        """

        energy_cost = 0.0
        for element in router_provenance:
            # only process per chip counters, not summary counters.
            if element.names[1] not in self._PER_CHIP_NAMES:
                continue

            # process MC packets
            if element.names[3] in self._MULTICAST_COUNTER_NAMES:
                energy_cost += float(element.value) * self.JOULES_PER_SPIKE

            # process p2p packets
            elif element.names[3] in self._PEER_TO_PEER_COUNTER_NAMES:
                energy_cost += \
                    float(element.value) * self.JOULES_PER_SPIKE * 2

            # process NN packets
            elif element.names[3] in self._NEAREST_NEIGHBOUR_COUNTER_NAMES:
                energy_cost += float(element.value) * self.JOULES_PER_SPIKE

            # process FR packets
            elif element.names[3] in self._FIXED_ROUTE_COUNTER_NAMES:
                energy_cost += \
                    float(element.value) * self.JOULES_PER_SPIKE * 2

        # detailed report print
        f.write("The packet cost is {} Joules\n".format(energy_cost))
        return energy_cost

    def _calculate_load_time_cost(
            self, pacman_provenance, machine, f, load_time,
            active_chips, n_frames):
        """ Energy usage from the loading phase

        :param pacman_provenance: provenance items from the PACMAN set
        :param machine: machine description
        :param f: file writer
        :param active_chips: the chips which have end user code in them
        :param load_time: the time of the entire load time phase in ms
        :return: load time energy value in Joules
        """
        # pylint: disable=too-many-arguments

        # find time in milliseconds
        total_time_ms = 0.0
        for element in pacman_provenance:
            if element.names[1] == "loading":
                total_time_ms += convert_time_diff_to_total_milliseconds(
                    element.value)

        # handle monitor core active cost
        # min between chips that are active and fixed monitor, as when 1
        # chip is used its one monitor, if more than 1 chip,
        # the ethernet connected chip and the monitor handling the read/write
        # this is checked by min
        energy_cost = (
            total_time_ms *
            min(self.N_MONITORS_ACTIVE_DURING_COMMS, len(active_chips)) *
            (self.MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD / 18))

        # handle all idle cores
        energy_cost += self._calculate_idle_cost(total_time_ms, machine)

        # handle time diff between load time and total laod phase of ASB
        energy_cost += (
            (load_time - total_time_ms) *
            len(list(machine.chips)) * self.MILLIWATTS_PER_IDLE_CHIP)

        # handle active routers etc
        active_router_cost = (
            load_time * n_frames * self.MILLIWATTS_PER_FRAME_ACTIVE_COST)

        # accumulate
        energy_cost += active_router_cost

        # detailed report write
        f.write(
            "The amount of time used during the loading process is {} "
            "milliseconds.\nAssumed only 2 monitor cores is executing that "
            "this point. We also assume that there is a baseline active "
            "router/cooling component that is using {} Joules. "
            "Overall the energy usage is {} Joules.\n".format(
                total_time_ms, active_router_cost, energy_cost))

        return energy_cost

    def _calculate_data_extraction_time_cost(
            self, pacman_provenance, machine, f, active_chips, n_frames):
        """ Data extraction cost

        :param pacman_provenance: provenance items from the PACMAN set
        :param machine: machine description
        :param f: file writer
        :param active_chips:
        :return: cost of data extraction in Joules
        """
        # pylint: disable=too-many-arguments

        # find time
        total_time_ms = 0.0
        for element in pacman_provenance:
            if (element.names[1] == "Execution" and element.names[2] !=
                    "run_time_of_FrontEndCommonApplicationRunner"):
                total_time_ms += convert_time_diff_to_total_milliseconds(
                    element.value)

        # min between chips that are active and fixed monitor, as when 1
        # chip is used its one monitor, if more than 1 chip,
        # the ethernet connected chip and the monitor handling the read/write
        # this is checked by min
        energy_cost = (
            total_time_ms *
            min(self.N_MONITORS_ACTIVE_DURING_COMMS, len(active_chips)) *
            self.MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD / 18)

        # add idle chip cost
        energy_cost += self._calculate_idle_cost(total_time_ms, machine)

        # handle active routers etc
        energy_cost_of_active_router = (
            total_time_ms * n_frames *
            self.MILLIWATTS_PER_FRAME_ACTIVE_COST)
        energy_cost += energy_cost_of_active_router

        # detailed report
        f.write(
            "The amount of time used during the data extraction process is {} "
            "milliseconds.\nAssumed only 2 monitor cores is executing at "
            "this point. We also assume that there is a baseline active "
            "router/cooling component that is using {} Joules. Hence the "
            "overall energy usage is {} Joules.\n".format(
                total_time_ms, energy_cost_of_active_router, energy_cost))

        return energy_cost

    def _calculate_idle_cost(self, time, machine):
        """ Calculate energy used by being idle.

        :param machine: machine description
        :param time: time machine was idle
        :type time: float
        :return: cost in joules
        """
        return time * machine.total_available_user_cores * (
                self.MILLIWATTS_PER_IDLE_CHIP / 18)

    def _calculate_power_down_cost(
            self, time, machine, machine_allocation_controller, version,
            n_frames):
        """ Calculate power down costs

        :param time: time powered down
        :param n_frames: number of frames used by this machine
        :return: energy in joules
        """
        # pylint: disable=too-many-arguments

        # if spalloc or hbp
        if machine_allocation_controller is not None:
            return time * n_frames * self.MILLIWATTS_FOR_FRAME_IDLE_COST
        # if 48 chip
        if version == 5 or version == 4:
            return time * self.MILLIWATTS_FOR_BOXED_48_CHIP_FRAME_IDLE_COST
        # if 4 chip
        if version == 3 or version == 2:
            return (len(list(machine.chips)) *
                    time * self.MILLIWATTS_PER_IDLE_CHIP)
        # boom
        raise ConfigurationException("don't know what to do here")

    @staticmethod
    def _calculate_n_frames(machine, machine_allocation_controller):
        """ Figures out how many frames are being used in this setup.\
            A key of cabinet,frame will be used to identify unique frame.

        :param machine: the machine object
        :param machine_allocation_controller: the spalloc job object
        :return: number of frames
        """

        # if not spalloc, then could be any type of board, but unknown cooling
        if machine_allocation_controller is None:
            return 0

        # if using spalloc in some form
        cabinet_frame = set()
        for ethernet_connected_chip in machine.ethernet_connected_chips:
            cabinet, frame, _ = machine_allocation_controller.where_is_machine(
                chip_x=ethernet_connected_chip.x,
                chip_y=ethernet_connected_chip.y)
            cabinet_frame.add((cabinet, frame))
        return len(list(cabinet_frame))
