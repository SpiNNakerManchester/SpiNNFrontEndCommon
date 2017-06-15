import os

from spinn_front_end_common.utility_models.\
    chip_power_monitor_machine_vertex import \
    ChipPowerMonitorMachineVertex
from spinn_front_end_common.utilities import exceptions

class FrontEndCommonEnergyReport(object):

    # given from indar measurements
    JULES_PER_MILLISECOND_PER_FPGA = 0.000584635
    # stated in papers (SpiNNaker: A 1-W 18 core system-on-Chip for
    # Massively-Parallel Neural Network Simulation)
    JULES_PER_MILLISECOND_PER_CHIP = 0.001
    # stated in papers (SpiNNaker: A 1-W 18 core system-on-Chip for
    # Massively-Parallel Neural Network Simulation)
    JULES_PER_SPIKE = 0.000000000800
    # stated in papers (SpiNNaker: A 1-W 18 core system-on-Chip for
    # Massively-Parallel Neural Network Simulation)
    JULES_PER_MILLISECOND_PER_IDLE_CHIP = 0.000360

    # energy report file name
    ENERGY_DETAILED_FILENAME = "Detailed_energy_report"
    ENERGY_SUMMARY_FILENAME = "energy_summary_report"

    def __call__(
            self, placements, machine, report_default_directory, version,
            spalloc_server, remote_spinnaker_url, time_scale_factor,
            machine_time_step, pacman_provenance, router_provenance,
            machine_graph, runtime, buffer_manager):
        """
        
        :param placements: 
        :param machine: 
        :param report_default_directory: 
        :param version: 
        :param spalloc_server:
        :param remote_spinnaker_url:
        :param time_scale_factor: 
        :param machine_time_step: 
        :param pacman_provenance: 
        :param router_provenance: 
        :param machine_graph: 
        :param buffer_manager:
        :return: 
        """

        detailed_report = os.path.join(
            report_default_directory, self.ENERGY_DETAILED_FILENAME)

        summary_report = os.path.join(
            report_default_directory, self.ENERGY_DETAILED_FILENAME)

        active_chip_cost = None
        idle_chip_cost = None
        fpga_cost = None
        packet_cost = None
        load_time_cost = None
        data_extraction_cost = None

        with open(detailed_report, "w") as output:
            active_chip_cost, idle_chip_cost, fpga_cost, packet_cost, \
                load_time_cost, data_extraction_cost = \
                self._write_detailed_report(
                    placements, machine, version, spalloc_server,
                    remote_spinnaker_url, time_scale_factor, machine_time_step,
                    pacman_provenance, router_provenance, machine_graph,
                    runtime, buffer_manager, output)

        load_time_in_milliseconds = pacman_provenance
        data_extraction_time_in_milliseconds = pacman_provenance

        with open(summary_report, "w") as output:
            self._write_summary_report(
                active_chip_cost, idle_chip_cost, fpga_cost, packet_cost,
                load_time_cost, data_extraction_cost, runtime,
                load_time_in_milliseconds,
                data_extraction_time_in_milliseconds, output)

    @staticmethod
    def _write_summary_report(
            active_chip_cost, idle_chip_cost, fpga_cost, packet_cost,
            load_time_cost, data_extraction_cost, runtime,
            load_time_in_milliseconds, data_extraction_time_in_milliseconds,
            output):

        # total the energy costs
        total_jules = (
            active_chip_cost + idle_chip_cost + fpga_cost + packet_cost +
            load_time_cost + data_extraction_cost)

        # deduce wattage from the runtime
        total_watts = total_jules / (
            (runtime + load_time_in_milliseconds +
             data_extraction_time_in_milliseconds) / 1000)

        output.write(
            "Summary energy file\n\n"
            "Energy used by active chips during runtime is {} Jules\n"
            "Energy used by inactive chipd during runtime is {} Jules\n"
            "Energy used by active FPGAs is {} Jules\n"
            "Energy used by packet transmissions is {} Jules\n"
            "Energy used during the loading process is {} Jules\n"
            "Energy used during the data extraction process is {} Jules\n"
            "Total energy used by the simulation is {} Jules or estimated {} "
            "Watts".format(
                active_chip_cost, idle_chip_cost, fpga_cost, packet_cost,
                load_time_cost, data_extraction_cost, total_jules,
                total_watts))

    def _write_detailed_report(
            self, placements, machine, version, spalloc_server,
            remote_spinnaker_url, time_scale_factor, machine_time_step,
            pacman_provenance, router_provenance, machine_graph, runtime,
            buffer_manager, output):
        """
        
        :param placements: 
        :param machine: 
        :param version: 
        :param spalloc_server:
        :param remote_spinnaker_url:
        :param time_scale_factor: 
        :param machine_time_step: 
        :param pacman_provenance: 
        :param router_provenance: 
        :param machine_graph: 
        :param buffer_manager:
        :param output: 
        :return: 
        """
        self._write_warning(output)

        # figure active chips
        active_chips = set()
        for placement in placements:
            active_chips.add(machine.get_chip_at(placement.x, placement.y))

        # figure out active chips idle time
        #machine_active_cost = 0.0
        #for chip in active_chips:
        #    machine_active_cost += self._calculate_chips_active_cost(
        #        chip, machine_graph, placements, machine_time_step,
        #        time_scale_factor, runtime, buffer_manager, output)

        # figure out idle chips
        #machine_idle_chips_cost = 0.0
        #for chip in machine.chips():
        #    if chip not in active_chips:
        #        machine_idle_chips_cost += self._calculate_chips_active_cost(
        #            chip, machine_graph, placements, machine_time_step,
        #            time_scale_factor, runtime, buffer_manager, output)

        # figure out packet cost
        packet_cost = 0.0
        for chip in machine.chips():
            packet_cost += self._router_packet_cost(
                chip, router_provenance, output)

        # figure FPGA cost
        fpga_cost = self._calulcate_fpga_cost(
            machine, version, spalloc_server, remote_spinnaker_url, runtime,
            machine_time_step, time_scale_factor, output)

        # figure load time cost
        load_time_cost = self._calculate_load_time_cost(pacman_provenance)

        # figure extraction time cost
        extraction_time_cost = \
            self._calculate_data_extraction_time_cost(pacman_provenance)

        return machine_active_cost, machine_idle_chips_cost, \
               fpga_cost, packet_cost, load_time_cost, extraction_time_cost

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
                self.JULES_PER_MILLISECOND_PER_CHIP,
                self.JULES_PER_MILLISECOND_PER_IDLE_CHIP,
                self.JULES_PER_SPIKE, self.JULES_PER_MILLISECOND_PER_FPGA))

    @staticmethod
    def _calculate_load_time_cost(pacman_provenance):
        return 0

    @staticmethod
    def _calculate_data_extraction_time_cost(pacman_provenance):
        return 0

    def _calulcate_fpga_cost(
            self, machine, version, spalloc_server, remote_spinnaker_url,
            runtime, machine_time_step, time_scale_factor, output):

        # if not spalloc, then could be any type of board
        if spalloc_server is None and remote_spinnaker_url is None:
            if version in range(2, 3):
                output.write(
                    "A Spinn {} board does not contain any FPGA's, and so "
                    "its energy cost is 0".format(version))
                return 0
            elif version in range(4, 5):
                if self._has_wrap_arounds(machine):
                    power_usage = (
                        runtime * machine_time_step * time_scale_factor *
                        self.JULES_PER_MILLISECOND_PER_FPGA)
                    output.write(
                        "The FPGA's on the Spinn {} board are turned on and "
                        "therefore the energy used by the FPGA is {}".format(
                            version, power_usage))
                    return power_usage
                else:
                    output.write(
                    "The FPGA's on the Spinn {} board are turned off and "
                    "therefore the energy used by the FPGA is 0".format(
                        version))
                    return 0
            else:
                raise exceptions.ConfigurationException(
                    "Do not know what the FPGA setup is for this version of "
                    "SpiNNaker machine.")
        else:

        return 0

    @staticmethod
    def _has_wrap_arounds(machine):
        pass

    def _calculate_chips_active_cost(
            self, chip, machine_graph, placements, machine_time_step,
            time_scale_factor, runtime, buffer_manager, output):
        """
        
        :param chip: 
        :param machine_graph: 
        :param placements: 
        :param machine_time_step: 
        :param time_scale_factor: 
        :param runtime: 
        :param buffer_manager: 
        :param output: 
        :return: 
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

                # check if vertex is a chip pwoer monitor
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
        cores_power_cost = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0,0.0, 0.0, 0.0, 0.0,
                            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        for recorded_measurement in recorded_measurements:
            for core in range(0, 18):
                cores_power_cost[core] += (
                    recorded_measurement[core] * time_for_recorded_sample *
                    self.JULES_PER_MILLISECOND_PER_CHIP)

        for core in range(0, 18):
            output.write(
                "processor {}:{}:{} used {} Jules of energy during the"
                " execution of the simulation".format(
                    chip.x, chip.y, core, cores_power_cost[core]))

        total_energy_cost = 0.0
        for core in cores_power_cost:
            total_energy_cost += cores_power_cost[core]
        return total_energy_cost

    def _router_packet_cost(self, chip, router_provenance, output):

        for element in router_provenance:
            print element
        return 0
