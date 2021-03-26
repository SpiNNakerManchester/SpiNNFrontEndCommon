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
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.utility_models import ChipPowerMonitorMachineVertex
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities.helpful_functions import (
    convert_time_diff_to_total_milliseconds)
from spinn_front_end_common.interface.interface_functions import (
    ComputeEnergyUsed)
from spinn_machine.machine import Machine

logger = FormatAdapter(logging.getLogger(__name__))


class EnergyReport(object):
    """ This class creates a report about the approximate total energy\
        consumed by a SpiNNaker job execution.
    """

    __slots__ = (
        "__report_dir", "__version", "__uses_spalloc", "__time_scale_factor")

    #: converter between joules to kilowatt hours
    JOULES_TO_KILOWATT_HOURS = 3600000

    # energy report file name
    _DETAILED_FILENAME = "detailed_energy_report.rpt"
    _SUMMARY_FILENAME = "summary_energy_report.rpt"

    def __init__(self, report_default_directory, version, spalloc_server,
                 remote_spinnaker_url, time_scale_factor):
        """
        :param str report_default_directory: location for reports
        :param int version: version of machine
        :param str spalloc_server: spalloc server IP
        :param str remote_spinnaker_url: remote SpiNNaker URL
        :param int time_scale_factor: the time scale factor
        """
        self.__report_dir = report_default_directory
        self.__version = version
        self.__uses_spalloc = bool(spalloc_server or remote_spinnaker_url)
        self.__time_scale_factor = time_scale_factor

    def write_energy_report(
            self, placements, machine, runtime, buffer_manager, power_used):
        """ Writes the report.

        :param ~pacman.model.placements.Placements placements: the placements
        :param ~spinn_machine.Machine machine: the machine
        :param int runtime:
        :param BufferManager buffer_manager:
        :param PowerUsed power_used:
        :rtype: None
        """
        # pylint: disable=too-many-arguments, too-many-locals
        if buffer_manager is None:
            logger.info("Skipping Energy report as no buffer_manager set")
            return

        # detailed report path
        detailed_report = os.path.join(
            self.__report_dir, self._DETAILED_FILENAME)

        # summary report path
        summary_report = os.path.join(
            self.__report_dir, self._SUMMARY_FILENAME)

        # figure runtime in milliseconds with time scale factor
        runtime_total_ms = runtime * self.__time_scale_factor

        # create detailed report
        with open(detailed_report, "w") as f:
            self._write_detailed_report(
                placements, machine, power_used, f, runtime_total_ms)

        # create summary report
        with open(summary_report, "w") as f:
            self._write_summary_report(runtime_total_ms, f, power_used)

    @classmethod
    def _write_summary_report(cls, runtime_total_ms, f, power_used):
        """ Write summary file

        :param int runtime_total_ms:
            Runtime with time scale factor taken into account
        :param ~io.TextIOBase f: file writer
        :param PowerUsed power_used:
        """
        # pylint: disable=too-many-arguments, too-many-locals

        # write summary data
        f.write("Summary energy file\n-------------------\n\n")
        f.write(
            "Energy used by chips during runtime is {} Joules {}\n".format(
                power_used.chip_energy_joules,
                cls.__report_time(runtime_total_ms / 1000)))
        f.write(
            "Energy used by FPGAs is {} Joules over the entire time the "
            "machine was booted {}\n".format(
                power_used.fpga_total_energy_joules,
                cls.__report_time(power_used.booted_time_secs)))
        f.write(
            "Energy used by FPGAs is {} Joules over the runtime period {}\n"
            .format(
                power_used.fpga_exec_energy_joules,
                cls.__report_time(runtime_total_ms / 1000)))
        f.write(
            "Energy used by outside router / cooling during the runtime "
            "period is {} Joules\n".format(power_used.baseline_joules))
        f.write(
            "Energy used by packet transmissions is {} Joules {}\n".format(
                power_used.packet_joules,
                cls.__report_time(power_used.total_time_secs)))
        f.write(
            "Energy used during the mapping process is {} Joules {}\n".format(
                power_used.mapping_joules,
                cls.__report_time(power_used.mapping_time_secs)))
        f.write(
            "Energy used by the data generation process is {} Joules {}\n"
            .format(
                power_used.data_gen_joules,
                cls.__report_time(power_used.data_gen_time_secs)))
        f.write(
            "Energy used during the loading process is {} Joules {}\n".format(
                power_used.loading_joules,
                cls.__report_time(power_used.loading_time_secs)))
        f.write(
            "Energy used during the data extraction process is {} Joules {}\n"
            .format(power_used.saving_joules, cls.__report_time(
                power_used.saving_time_secs)))
        f.write(
            "Total energy used by the simulation over {} milliseconds is:\n"
            "     {} Joules, or\n"
            "     {} estimated average Watts, or\n"
            "     {} kWh\n".format(
                power_used.total_time_secs * 1000,
                power_used.total_energy_joules,
                power_used.total_energy_joules / power_used.total_time_secs,
                power_used.total_energy_joules /
                cls.JOULES_TO_KILOWATT_HOURS))

    @staticmethod
    def __report_time(time):
        """
        :param float time:
        :rtype: str
        """
        if time < 1:
            return "(over {} milliseconds)".format(time * 1000)
        else:
            return "(over {} seconds)".format(time)

    def _write_detailed_report(
            self, placements, machine, power_used, f, runtime_total_ms):
        """ Write detailed report and calculate costs

        :param ~.Placements placements: placements
        :param ~.Machine machine: machine representation
        :param PowerUsed power_used:
        :param ~io.TextIOBase f: file writer
        :param float runtime_total_ms:
            total runtime with time scale factor taken into account
        """
        # pylint: disable=too-many-arguments, too-many-locals

        # write warning about accuracy etc
        self._write_warning(f)

        # figure out packet cost
        f.write("The packet cost is {} Joules\n".format(
            power_used.packet_joules))

        # figure FPGA cost over all booted and during runtime cost
        self._write_fpga_cost(power_used, f)

        # figure load time cost
        self._write_load_time_cost(power_used, f)

        # figure extraction time cost
        self._write_data_extraction_time_cost(power_used, f)

        # figure out active chips idle time
        active_chips = set()
        for placement in placements:
            if not isinstance(placement.vertex, ChipPowerMonitorMachineVertex):
                active_chips.add(machine.get_chip_at(placement.x, placement.y))
        for chip in active_chips:
            self._write_chips_active_cost(
                chip, placements, runtime_total_ms, power_used, f)

    def _write_warning(self, f):
        """ Writes the warning about this being only an estimate

        :param ~io.TextIOBase f: the writer
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
                ComputeEnergyUsed.MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD,
                ComputeEnergyUsed.MILLIWATTS_PER_IDLE_CHIP,
                ComputeEnergyUsed.JOULES_PER_SPIKE,
                ComputeEnergyUsed.MILLIWATTS_PER_FPGA))

    def _write_fpga_cost(self, power_used, f):
        """ FPGA cost calculation

        :param PowerUsed power_used: the runtime
        :param ~io.TextIOBase f: the file writer
        """

        # if not spalloc, then could be any type of board
        if not self.__uses_spalloc:
            # if a spinn2 or spinn3 (4 chip boards) then they have no fpgas
            if int(self.__version) in (2, 3):
                f.write(
                    "A SpiNN-{} board does not contain any FPGA's, and so "
                    "its energy cost is 0 \n".format(self.__version))
                return
            elif int(self.__version) not in (4, 5):
                # no idea where we are; version unrecognised
                raise ConfigurationException(
                    "Do not know what the FPGA setup is for this version of "
                    "SpiNNaker machine.")

            # if a spinn4 or spinn5 board, need to verify if wrap-arounds
            # are there, if not then assume fpgas are turned off.
            if power_used.num_fpgas == 0:
                # no active fpgas
                f.write(
                    "The FPGA's on the SpiNN-{} board are turned off and "
                    "therefore the energy used by the FPGA is 0\n".format(
                        self.__version))
                return
            # active fpgas; fall through to shared main part report

        # print out as needed for spalloc and non-spalloc versions
        if self.__version is None:
            f.write(
                "{} FPGAs on the Spalloc-ed boards are turned on and "
                "therefore the energy used by the FPGA during the entire time "
                "the machine was booted (which was {} ms) is {}. "
                "The usage during execution was {}".format(
                    power_used.num_fpgas, power_used.total_time_secs * 1000,
                    power_used.fpga_total_energy_joules,
                    power_used.fpga_exec_energy_joules))
        else:
            f.write(
                "{} FPGA's on the SpiNN-{} board are turned on and "
                "therefore the energy used by the FPGA during the entire time "
                "the machine was booted (which was {} ms) is {}. "
                "The usage during execution was {}".format(
                    power_used.num_fpgas, self.__version,
                    power_used.total_time_secs * 1000,
                    power_used.fpga_total_energy_joules,
                    power_used.fpga_exec_energy_joules))

    @staticmethod
    def _write_chips_active_cost(
            chip, placements, runtime_total_ms, power_used, f):
        """ Figure out the chip active cost during simulation

        :param ~.Chip chip: the chip to consider
        :param ~.Placements placements: placements
        :param float runtime_total_ms:
        :param PowerUsed power_used:
        :param ~io.TextIOBase f: file writer
        :return: energy cost
        """

        f.write("\n")

        # detailed report print out
        for core in range(Machine.DEFAULT_MAX_CORES_PER_CHIP):
            if placements.is_processor_occupied(chip.x, chip.y, core):
                vertex = placements.get_vertex_on_processor(
                    chip.x, chip.y, core)
                label = " (running {})".format(vertex.label)
            else:
                label = ""
            energy = power_used.get_core_active_energy_joules(
                chip.x, chip.y, core)
            f.write(
                "processor {}:{}:{}{} used {} Joules of energy by "
                "being active during the execution of the simulation\n".format(
                    chip.x, chip.y, core, label, energy))

        # TAKE INTO ACCOUNT IDLE COST
        idle_cost = (
            runtime_total_ms * ComputeEnergyUsed.MILLIWATTS_PER_IDLE_CHIP)

        f.write(
            "The chip at {},{} used {} Joules of energy for by being idle "
            "during the execution of the simulation\n".format(
                chip.x, chip.y, idle_cost))

    @staticmethod
    def _write_load_time_cost(power_used, f):
        """ Energy usage from the loading phase

        :param PowerUsed power_used:
        :param ~io.TextIOBase f: file writer
        """

        # find time in milliseconds
        total_time_ms = 0.0
        for element in power_used._algorithm_timing_provenance:
            if element.names[1] == "loading":
                total_time_ms += convert_time_diff_to_total_milliseconds(
                    element.value)

        # handle active routers etc
        active_router_cost = (
            power_used.loading_time_secs * 1000 * power_used.num_frames *
            ComputeEnergyUsed.MILLIWATTS_PER_FRAME_ACTIVE_COST)

        # detailed report write
        f.write(
            "The amount of time used during the loading process is {} "
            "milliseconds.\nAssumed only 2 monitor cores is executing that "
            "this point. We also assume that there is a baseline active "
            "router/cooling component that is using {} Joules. "
            "Overall the energy usage is {} Joules.\n".format(
                total_time_ms, active_router_cost,
                power_used.loading_joules))

    @staticmethod
    def _write_data_extraction_time_cost(power_used, f):
        """ Data extraction cost

        :param PowerUsed power_used:
        :param ~io.TextIOBase f: file writer
        """

        # find time
        total_time_ms = 0.0
        for element in power_used._algorithm_timing_provenance:
            if (element.names[1] == "Execution" and element.names[2] !=
                    "run_time_of_FrontEndCommonApplicationRunner"):
                total_time_ms += convert_time_diff_to_total_milliseconds(
                    element.value)

        # handle active routers etc
        energy_cost_of_active_router = (
            total_time_ms * power_used.num_frames *
            ComputeEnergyUsed.MILLIWATTS_PER_FRAME_ACTIVE_COST)

        # detailed report
        f.write(
            "The amount of time used during the data extraction process is {} "
            "milliseconds.\nAssumed only 2 monitor cores is executing at "
            "this point. We also assume that there is a baseline active "
            "router/cooling component that is using {} Joules. Hence the "
            "overall energy usage is {} Joules.\n".format(
                total_time_ms, energy_cost_of_active_router,
                power_used.saving_joules))
