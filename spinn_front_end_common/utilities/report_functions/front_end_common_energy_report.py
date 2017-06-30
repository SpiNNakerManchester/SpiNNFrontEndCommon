import os

from spinn_front_end_common.utility_models.\
    chip_power_monitor_machine_vertex import \
    ChipPowerMonitorMachineVertex
from spinn_front_end_common.utilities import exceptions, helpful_functions


class FrontEndCommonEnergyReport(object):

    # given from indar measurements
    JULES_PER_MILLISECOND_PER_FPGA = 0.000584635

    # stated in papers (SpiNNaker: A 1-W 18 core system-on-Chip for
    # Massively-Parallel Neural Network Simulation)
    JULES_PER_SPIKE = 0.000000000800

    # stated in papers (SpiNNaker: A 1-W 18 core system-on-Chip for
    # Massively-Parallel Neural Network Simulation)
    JULES_PER_MILLISECOND_PER_IDLE_CHIP = 0.000360

    # stated in papers (SpiNNaker: A 1-W 18 core system-on-Chip for
    # Massively-Parallel Neural Network Simulation)
    JULES_PER_MILLISECOND_PER_CHIP_ACTIVE_OVERHEAD = \
        0.001 - JULES_PER_MILLISECOND_PER_IDLE_CHIP

    # converter between jules to Killiwatt hours
    JULES_TO_KILLIWATT_HOURS = 3600000

    # base energy of power off machine (based off real measurements from
    # Rowley) found in paper (Performance comparison of digital neuromorphic
    # hardware (SpiNNaker) and neural network simulation software (NEST) on
    # the example of a full-scale cortical microcircuit model)
    JULES_PER_MILLISECOND_PER_POWER_DOWN_BOARD = 0.00000000906

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
            execute_time, dsg_time, extraction_time):
        """ main call

        :param placements: the placements
        :param machine: the machine
        :param report_default_directory: location for reports
        :param version: version of machine
        :param spalloc_server: spalloc server ip
        :param remote_spinnaker_url: remote spinnaker url
        :param time_scale_factor: the time scale factor
        :param machine_time_step: the machine time step
        :param pacman_provenance: the pacman provenance
        :param router_provenance: the router provenance
        :param machine_graph: the machine graph
        :param buffer_manager: the buffer manager
        :param mapping_time:
        :param load_time:
        :param execute_time:
        :param dsg_time:
        :param extraction_time:
        :rtype: None
        """

        detailed_report = os.path.join(
            report_default_directory, self.ENERGY_DETAILED_FILENAME)

        summary_report = os.path.join(
            report_default_directory, self.ENERGY_SUMMARY_FILENAME)

        total_time = (
            execute_time + load_time + extraction_time + dsg_time +
            mapping_time)

        with open(detailed_report, "w") as output:
            active_chip_cost, fpga_cost, packet_cost, mapping_cost, \
                load_time_cost, data_extraction_cost, dsg_cost = \
                self._write_detailed_report(
                    placements, machine, version, spalloc_server,
                    remote_spinnaker_url, time_scale_factor, machine_time_step,
                    pacman_provenance, router_provenance, runtime, dsg_time,
                    buffer_manager, output, load_time, mapping_time,
                    total_time)

        with open(summary_report, "w") as output:
            self._write_summary_report(
                active_chip_cost, fpga_cost, packet_cost, mapping_cost,
                load_time_cost, data_extraction_cost, runtime, output,
                mapping_time, load_time, dsg_time, dsg_cost,
                extraction_time, total_time)

    @staticmethod
    def _write_summary_report(
            active_chip_cost, fpga_cost, packet_cost, mapping_cost,
            load_time_cost, data_extraction_cost, runtime, output,
            mapping_time, load_time, dsg_time, dsg_cost,
            extraction_time, total_time):
        """ write summary file

        :param active_chip_cost: active chip cost
        :param fpga_cost: fpga cost
        :param mapping_time: the time taken by the mapping process in ms
        :param mapping_cost: the energy used by the mapping process
        :param packet_cost: packet cost
        :param load_time_cost: load time cost
        :param data_extraction_cost: data extraction cost
        :param runtime: runtime
        :param output: file writer
        :rtype: None
        """

        # total the energy costs
        total_jules = (
            active_chip_cost + fpga_cost + packet_cost + mapping_cost +
            load_time_cost + data_extraction_cost + dsg_cost)

        # deduce wattage from the runtime
        total_watts = total_jules / (total_time / 1000)

        killawatt_hour = \
            total_jules / FrontEndCommonEnergyReport.JULES_TO_KILLIWATT_HOURS

        output.write(
            "Summary energy file\n\n"
            "Energy used by chips during runtime is {} Joules over {} "
            "milliseconds\n"
            "Energy used by FPGAs is {} Joules over {} milliseconds \n"
            "Energy used by packet transmissions is {} Joules over {} "
            "milliseconds\n"
            "Energy used during the mapping process is {} Joules over {} "
            "milliseconds\n"
            "Energy used by the data generation process is {} Joules over {} "
            "milliseconds\n"
            "Energy used during the loading process is {} Joules over {} "
            "milliseconds\n"
            "Energy used during the data extraction process is {} Jules over "
            "{} milliseconds\n"
            "Total energy used by the simulation over {} milliseconds is: \n"
            "     {} Joules or \n"
            "     {} estimated average Watts or \n"
            "     {} kWh\n".format(
                active_chip_cost, runtime, fpga_cost, runtime, packet_cost,
                total_time, mapping_cost, mapping_time, dsg_cost, dsg_time,
                load_time_cost, load_time, data_extraction_cost,
                extraction_time, total_time, total_jules, total_watts,
                killawatt_hour))

    def _write_detailed_report(
            self, placements, machine, version, spalloc_server,
            remote_spinnaker_url, time_scale_factor, machine_time_step,
            pacman_provenance, router_provenance, runtime, dsg_time,
            buffer_manager, output, load_time, mapping_time, total_runtime):
        """ write detailed report and calculate costs

        :param placements: placements
        :param machine: machine rep
        :param version: machine version
        :param spalloc_server: spalloc server
        :param remote_spinnaker_url: remote spinnaker url
        :param time_scale_factor: time scale factor
        :param machine_time_step: machine time step
        :param pacman_provenance: provenance generated by pacman
        :param router_provenance: provenance generated by the router
        :param buffer_manager: buffer manager
        :param output: file writer
        :return: machine_active_cost, machine_idle_chips_cost, \
            fpga_cost, packet_cost, load_time_cost, extraction_time_cost
        """
        self._write_warning(output)

        # figure active chips
        active_chips = set()
        for placement in placements:
            if not isinstance(placement.vertex, ChipPowerMonitorMachineVertex):
                active_chips.add(machine.get_chip_at(placement.x, placement.y))

        # figure out packet cost
        packet_cost = self._router_packet_cost(router_provenance, output)

        # figure FPGA cost
        fpga_cost = self._calculate_fpga_cost(
            machine, version, spalloc_server, remote_spinnaker_url,
            total_runtime, runtime, machine_time_step, time_scale_factor,
            output)

        # figure load time cost
        load_time_cost = self._calculate_load_time_cost(
            pacman_provenance, machine, output, load_time, active_chips)

        mapping_cost = self._calculate_idle_cost(mapping_time, machine)

        dsg_cost = self._calculate_idle_cost(dsg_time, machine)

        # figure extraction time cost
        extraction_time_cost = \
            self._calculate_data_extraction_time_cost(
                pacman_provenance, machine, output, active_chips)

        # figure out active chips idle time
        machine_active_cost = 0.0
        for chip in active_chips:
            machine_active_cost += self._calculate_chips_active_cost(
                chip, placements, buffer_manager, output, machine)

        return machine_active_cost, fpga_cost, packet_cost, mapping_cost, \
            load_time_cost, extraction_time_cost, dsg_cost

    def _write_warning(self, output):
        """ writes the warning about this being only an estimate

        :param output: the writer
        :rtype: None
        """

        output.write(
            "This report is based off energy estimates for individual "
            "components of the SpiNNaker machine. It is not meant to be "
            "completely accurate. But does use provenance data gathered from"
            " the machine to estimate the energy usage and therefore should "
            "be within the ball park.\n\n\n")
        output.write(
            "The energy components we use are as follows: \n\n"
            "The energy usage for a chip when all cores are 100% active for"
            " a millisecond is {} Jules\n"
            "The energy usage for a chip when all cores are not active for a "
            "millisecond is {} Jules\n"
            "The energy used by the machine for firing a packet is {} Jules\n"
            "The energy used by each active FPGA per millisecond is {} "
            "Jules.\n\n\n"
            .format(
                self.JULES_PER_MILLISECOND_PER_CHIP_ACTIVE_OVERHEAD,
                self.JULES_PER_MILLISECOND_PER_IDLE_CHIP,
                self.JULES_PER_SPIKE, self.JULES_PER_MILLISECOND_PER_FPGA))

    def _calculate_fpga_cost(
            self, machine, version, spalloc_server, remote_spinnaker_url,
            total_runtime, runtime, machine_time_step, time_scale_factor,
            output):
        """ fpga cost calculation

        :param machine: machine rep
        :param version: machine version
        :param spalloc_server: spalloc server ip
        :param remote_spinnaker_url: remote spinnaker
        :param total_runtime: runtime
        :param machine_time_step: the machine time step
        :param time_scale_factor: the time scale factor
        :param output: the file writer
        :return: power usage of fpgas
        """

        # if not spalloc, then could be any type of board
        if spalloc_server is None and remote_spinnaker_url is None:

            # if a spinn2 or spinn3 (4 chip boards) then they have no fpgas
            if int(version) == 2 or int(version) == 3:
                output.write(
                    "A Spinn {} board does not contain any FPGA's, and so "
                    "its energy cost is 0 \n".format(version))
                return 0

            # if the spinn4 or spinn5 board, need to verify if wrap arounds
            # are there, if not then assume fppga's are turned off.
            elif int(version) == 4 or int(version) == 5:

                # how many fpgas are active
                n_operational_fpgas = self._board_n_operational_fpgas(
                    machine, machine.ethernet_connected_chips[0])

                # active fpgas
                if n_operational_fpgas > 0:
                    return self._print_out_fpga_cost(
                        total_runtime, runtime, machine_time_step,
                        time_scale_factor, n_operational_fpgas, output,
                        version)
                else:  # no active fpgas
                    output.write(
                        "The FPGA's on the Spinn {} board are turned off and "
                        "therefore the energy used by the FPGA is 0\n".format(
                            version))
                    return 0
            else:  # no idea where we are
                raise exceptions.ConfigurationException(
                    "Do not know what the FPGA setup is for this version of "
                    "SpiNNaker machine.")
        else:  # spalloc machine, need to check each board
            total_fpgas = 0
            for ethernet_connected_chip in machine.ethernet_connected_chips:
                total_fpgas += self._board_n_operational_fpgas(
                    machine, ethernet_connected_chip)
            return self._print_out_fpga_cost(
                total_runtime, runtime, machine_time_step, time_scale_factor,
                total_fpgas, output, version)

    def _print_out_fpga_cost(
            self, total_runtime, runtime, machine_time_step, time_scale_factor,
            n_operational_fpgas, output, version):
        """ prints out to file and returns cost

        :param runtime: runtime in ms
        :param machine_time_step: machine time step
        :param time_scale_factor: time scale factor
        :param n_operational_fpgas: n operational fpgas
        :param output: file writer
        :param version: machine version
        :return: power usage
        """
        power_usage = (
            ((runtime * machine_time_step * time_scale_factor) +
             total_runtime) * self.JULES_PER_MILLISECOND_PER_FPGA *
            n_operational_fpgas)
        output.write(
            "{} FPGA's on the Spinn {} board are turned on and "
            "therefore the energy used by the FPGA is {}".format(
                n_operational_fpgas, version, power_usage))
        return power_usage

    def _board_n_operational_fpgas(self, machine, ethernet_connected_chip):
        """ figures fpgas on

        :param machine: spinnaker machine
        :param ethernet_connected_chip: the ethernet chip to look from
        :return: number of fpgas on, on this board
        """

        # positions to check for active links
        left_additions = [[0, 0], [0, 1], [0, 2], [0, 3], [0, 4]]
        right_additions = [[7, 3], [7, 4], [7, 5], [7, 6], [7, 7]]
        top_additions = [[4, 7], [5, 7], [6, 7], [7, 7]]
        bottom_additions = [[0, 0], [1, 0], [2, 0], [3, 0], [4, 0]]
        top_left_additions = [[0, 3], [1, 4], [2, 5], [3, 6], [4, 7]]
        bottom_right_additions = [[0, 4], [1, 5], [2, 6], [3, 7]]

        machine_max_x = machine.max_chip_x
        machine_max_y = machine.max_chip_y

        ethernet_chip_x = ethernet_connected_chip.x
        ethernet_chip_y = ethernet_connected_chip.y

        # bottom left, bottom
        fpga_0 = self._deduce_fpga(
            [bottom_additions, bottom_right_additions], [[5, 4], [0, 5]],
            machine_max_x, machine_max_y, ethernet_chip_x, ethernet_chip_y,
            machine)
        # left, and top right
        fpga_1 = self._deduce_fpga(
            [left_additions, top_left_additions], [[3, 4], [3, 2]],
            machine_max_x, machine_max_y, ethernet_chip_x, ethernet_chip_y,
            machine)
        # top and right
        fpga_2 = self._deduce_fpga(
            [top_additions, right_additions], [[2, 1], [0, 1]],
            machine_max_x, machine_max_y, ethernet_chip_x, ethernet_chip_y,
            machine)
        return fpga_1 + fpga_0 + fpga_2

    @staticmethod
    def _deduce_fpga(
            shifts, overall_link_ids, machine_max_x, machine_max_y,
            ethernet_chip_x, ethernet_chip_y, machine):
        """ figure each fpga on or not

        :param shifts: shifts from ethernet to find a fpga edge
        :param overall_link_ids: which link ids to check
        :param machine_max_x: max machine x
        :param machine_max_y: max machine y
        :param ethernet_chip_x: ethernet chip x
        :param ethernet_chip_y: ethernet chip y
        :param machine: machine rep
        :return: 0 if not on, 1 if on
        """
        for shift_group, link_ids in zip(shifts, overall_link_ids):
            for shift in shift_group:
                new_x = (ethernet_chip_x + shift[0]) % (machine_max_x + 1)
                new_y = (ethernet_chip_y + shift[1]) % (machine_max_y + 1)
                chip = machine.get_chip_at(new_x, new_y)
                if chip is not None:
                    for link_id in link_ids:
                        link = chip.router.get_link(link_id)
                        if link is not None:
                            return 1
        return 0

    def _calculate_chips_active_cost(
            self, chip, placements, buffer_manager, output, machine):
        """ figure chip active cost during sim

        :param chip: the chip to consider
        :param placements: placements
        :param buffer_manager: buffer manager
        :param output: file writer
        :return: energy cost
        """

        # locate chip power monitor
        chip_power_monitor = None

        # start at top, as more likely it was placed on the top
        processor_id = 18
        while chip_power_monitor is None:
            processor = chip.get_processor_with_id(processor_id)
            if (processor is not None and
                    placements.is_processor_occupied(
                        chip.x, chip.y, processor_id)):

                # check if vertex is a chip power monitor
                vertex = placements.get_vertex_on_processor(
                    chip.x, chip.y, processor_id)
                if isinstance(vertex, ChipPowerMonitorMachineVertex):
                    chip_power_monitor = vertex
            processor_id -= 1

        # get recordings from the chip power monitor
        recorded_measurements = chip_power_monitor.get_recorded_data(
            placement=placements.get_placement_of_vertex(chip_power_monitor),
            buffer_manager=buffer_manager)
        time_for_recorded_sample = (
            chip_power_monitor.sampling_frequency *
            chip_power_monitor.n_samples_per_recording) / 1000
        cores_power_cost = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        for recorded_measurement in recorded_measurements:
            for core in range(0, 18):
                cores_power_cost[core] += (
                    recorded_measurement[core] * time_for_recorded_sample *
                    (self.JULES_PER_MILLISECOND_PER_CHIP_ACTIVE_OVERHEAD / 18))

        for core in range(0, 18):
            output.write(
                "processor {}:{}:{} used {} Jules of energy by being active "
                "during the execution of the simulation\n".format(
                    chip.x, chip.y, core, cores_power_cost[core]))

        total_energy_cost = 0.0
        for core_power_usage in cores_power_cost:
            total_energy_cost += core_power_usage

        # TAKE INTO ACCOUNT IDLE COST
        idle_cost = (
            time_for_recorded_sample * len(recorded_measurements) *
            machine.total_cores * (
                self.JULES_PER_MILLISECOND_PER_IDLE_CHIP / 18))

        total_energy_cost += idle_cost

        output.write(
            "The machine used {} Jules of energy by being idle "
            "during the execution of the simulation".format(idle_cost))

        return total_energy_cost

    def _router_packet_cost(self, router_provenance, output):
        """ packet cost, includes MC, P2P, FR, NN packets

        :param router_provenance: the provenance gained from the router
        :param output: file writer
        :rtype: energy usage value
        """

        energy_cost = 0.0
        for element in router_provenance:

            # only get per chip counters, not summary counters.
            if (element.names[1] == "expected_routers" or
                    element.names[1] == "unexpected_routers"):

                # process multicast packets
                if (element.names[3] == "Local_Multicast_Packets" or
                        element.names[3] == "External_Multicast_Packets" or
                        element.names[3] == "Reinjected"):
                    energy_cost += float(element.value) * self.JULES_PER_SPIKE

                # process p2p packets
                elif (element.names[3] == "Local_P2P_Packets" or
                        element.names[3] == "External_P2P_Packets"):
                    energy_cost += \
                        float(element.value) * self.JULES_PER_SPIKE * 2

                # process NN packets
                elif (element.names[3] == "Local_NN_Packets" or
                        element.names[3] == "External_NN_Packets"):
                    energy_cost += float(element.value) * self.JULES_PER_SPIKE

                elif (element.names[3] == "Local_FR_Packets" or
                        element.names[3] == "External_FR_Packets"):
                    energy_cost += \
                        float(element.value) * self.JULES_PER_SPIKE * 2

        # process
        output.write("The packet cost is {} Jules\n".format(energy_cost))
        return energy_cost

    def _calculate_load_time_cost(
            self, pacman_provenance, machine, output, load_time,
            active_chips):
        """ energy usage from the loading phase

        :param pacman_provenance: provenance items from the pacman set
        :param machine: machine rep
        :param output: file writer
        :param active_chips: the chips which have end user code in them
        :param load_time: the time of the entire load time phase in ms
        :return: load time energy value
        """

        total_milliseconds = 0.0
        loading_algorithms = list()
        for element in pacman_provenance:
            if element.names[1] == "loading":
                loading_algorithms.append(element)

        for element in loading_algorithms:
            total_milliseconds += \
                helpful_functions.convert_time_diff_to_total_milliseconds(
                    element.value)

        # handle monitor core active cost
        # min between chips that are active and fixed monitor, as when 1
        # chip is used its one monitor, if more than 1 chip,
        # the ethernet connected chip and the monitor handling the read/write
        # this is checked by min
        energy_cost = (
            total_milliseconds *
            min(self.N_MONITORS_ACTIVE_DURING_COMMS, len(active_chips)) *
            (self.JULES_PER_MILLISECOND_PER_CHIP_ACTIVE_OVERHEAD / 18))

        # handle all idle cores
        energy_cost += self._calculate_idle_cost(total_milliseconds, machine)

        diff_of_algorithms_and_boiler = total_milliseconds - load_time
        energy_cost += (
            diff_of_algorithms_and_boiler * (
                len(list(machine.chips)) *
                self.JULES_PER_MILLISECOND_PER_IDLE_CHIP))

        output.write(
            "The amount of time used during the loading process is {} "
            "milliseconds.\n Assumed only monitor core is executing that this"
            " point, so the energy usage is {} Jules \n".format(
                total_milliseconds, energy_cost))

        return energy_cost

    def _calculate_data_extraction_time_cost(
            self, pacman_provenance, machine, output, active_chips):
        """ data extraction cost

        :param pacman_provenance: provenance items from the pacman set
        :param machine: machine rep
        :param output: file writer
        :param active_chips:
        :return: cost of data extraction
        """

        total_milliseconds = 0.0
        extraction_algorithms = list()
        for element in pacman_provenance:
            if element.names[1] == "Execution":
                if not (element.names[2] ==
                        "run_time_of_FrontEndCommonApplicationRunner"):
                    extraction_algorithms.append(element)

        for element in extraction_algorithms:
            total_milliseconds += \
                helpful_functions.convert_time_diff_to_total_milliseconds(
                    element.value)

        # min between chips that are active and fixed monitor, as when 1
        # chip is used its one monitor, if more than 1 chip,
        # the ethernet connected chip and the monitor handling the read/write
        # this is checked by min
        energy_cost = (
            total_milliseconds *
            min(self.N_MONITORS_ACTIVE_DURING_COMMS, len(active_chips)) *
            (self.JULES_PER_MILLISECOND_PER_CHIP_ACTIVE_OVERHEAD / 18))

        energy_cost += self._calculate_idle_cost(total_milliseconds, machine)

        output.write(
            "The amount of time used during the data extraction process is {} "
            "milliseconds.\n Assumed only monitor core is executing that this"
            " point, so the energy usage is {} Jules \n".format(
                total_milliseconds, energy_cost))

        return energy_cost

    def _calculate_idle_cost(self, time, machine):
        """ calculate energy used by being idle

        :param machine: machine object
        :param time: time machine was idle
        :return: cost in jules
        """
        return time * machine.total_available_user_cores * (
                self.JULES_PER_MILLISECOND_PER_IDLE_CHIP / 18)
