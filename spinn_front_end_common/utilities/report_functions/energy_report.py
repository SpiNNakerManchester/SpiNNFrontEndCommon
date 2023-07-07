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
import os
from spinn_utilities.config_holder import (get_config_int, get_config_str)
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance import (
    FecTimer, GlobalProvenance, TimerCategory)
from spinn_front_end_common.utility_models import ChipPowerMonitorMachineVertex
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.interface.interface_functions.compute_energy_used\
    import (JOULES_PER_SPIKE, MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD,
            MILLIWATTS_PER_FRAME_ACTIVE_COST, MILLIWATTS_PER_FPGA,
            MILLIWATTS_PER_IDLE_CHIP)
from spinn_machine.machine import Machine

logger = FormatAdapter(logging.getLogger(__name__))


class EnergyReport(object):
    """
    This class creates a report about the approximate total energy
    consumed by a SpiNNaker job execution.
    """

    __slots__ = ()

    #: converter between joules to kilowatt hours
    JOULES_TO_KILOWATT_HOURS = 3600000

    # energy report file name
    _DETAILED_FILENAME = "detailed_energy_report.rpt"
    _SUMMARY_FILENAME = "summary_energy_report.rpt"

    def write_energy_report(self, power_used):
        """
        Writes the report.

        :param ~spinn_machine.Machine machine: the machine
        :param PowerUsed power_used:
        """
        report_dir = FecDataView.get_run_dir_path()

        # detailed report path
        detailed_report = os.path.join(report_dir, self._DETAILED_FILENAME)

        # summary report path
        summary_report = os.path.join(report_dir, self._SUMMARY_FILENAME)

        # create detailed report
        with open(detailed_report, "w", encoding="utf-8") as f:
            self._write_detailed_report(power_used, f)

        # create summary report
        with open(summary_report, "w", encoding="utf-8") as f:
            self._write_summary_report(f, power_used)

    @classmethod
    def _write_summary_report(cls, f, power_used):
        """
        Write summary file.

        :param ~io.TextIOBase f: file writer
        :param PowerUsed power_used:
        """
        # pylint: disable=too-many-arguments, too-many-locals

        # figure runtime in milliseconds with time scale factor
        runtime_total_ms = (
                FecDataView.get_current_run_time_ms() *
                FecDataView.get_time_scale_factor())

        # write summary data
        f.write("Summary energy file\n-------------------\n\n")
        f.write(
            "Energy used by chips during runtime is "
            f"{power_used.chip_energy_joules} Joules "
            f"{cls.__report_time(runtime_total_ms / 1000)}\n")
        f.write(
            f"Energy used by FPGAs is {power_used.fpga_total_energy_joules} "
            "Joules over the entire time the machine was booted "
            f"{cls.__report_time(power_used.booted_time_secs)}\n")
        f.write(
            f"Energy used by FPGAs is {power_used.fpga_exec_energy_joules} "
            "Joules over the runtime period "
            f"{cls.__report_time(runtime_total_ms / 1000)}\n")
        f.write(
            "Energy used by outside router / cooling during the runtime "
            f"period is {power_used.baseline_joules} Joules\n")
        f.write(
            "Energy used by packet transmissions is "
            f"{power_used.packet_joules} Joules "
            f"{cls.__report_time(power_used.total_time_secs)}\n")
        f.write(
            "Energy used during the mapping process is "
            f"{power_used.mapping_joules} Joules "
            f"{cls.__report_time(power_used.mapping_time_secs)}\n")
        f.write(
            "Energy used by the data generation process is "
            f"{power_used.data_gen_joules} Joules "
            f"{cls.__report_time(power_used.data_gen_time_secs)}\n")
        f.write(
            "Energy used during the loading process is "
            f"{power_used.loading_joules} Joules "
            f"{cls.__report_time(power_used.loading_time_secs)}\n")
        f.write(
            "Energy used during the data extraction process is "
            f"{power_used.saving_joules} Joules "
            f"{cls.__report_time(power_used.saving_time_secs)}\n")
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
            return f"(over {time * 1000} milliseconds)"
        else:
            return f"(over {time} seconds)"

    def _write_detailed_report(self, power_used, f):
        """
        Write detailed report and calculate costs.

        :param PowerUsed power_used:
        :param ~io.TextIOBase f: file writer
        """
        runtime_total_ms = (
                FecDataView.get_current_run_time_ms() *
                FecDataView.get_time_scale_factor())

        # write warning about accuracy etc
        self._write_warning(f)

        # figure out packet cost
        f.write(f"The packet cost is {power_used.packet_joules} Joules\n")

        # figure FPGA cost over all booted and during runtime cost
        self._write_fpga_cost(power_used, f)

        # figure load time cost
        self._write_load_time_cost(power_used, f)

        # figure extraction time cost
        self._write_data_extraction_time_cost(power_used, f)

        # sort what to report by chip
        active_chips = defaultdict(dict)
        for placement in FecDataView.iterate_placements_by_vertex_type(
                ChipPowerMonitorMachineVertex):
            labels = active_chips[placement.x, placement.y]
            labels[placement.p] = placement.vertex.label
        for xy in active_chips:
            self._write_chips_active_cost(
                xy, active_chips[xy], runtime_total_ms, power_used, f)

    def _write_warning(self, f):
        """
        Writes the warning about this being only an estimate.

        :param ~io.TextIOBase f: the writer
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
            f"a millisecond is {MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD} Joules.\n"
            "The energy usage for a chip when all cores are not active for a "
            f"millisecond is {MILLIWATTS_PER_IDLE_CHIP} Joules.\n"
            "The energy used by the machine for firing a packet is "
            f"{JOULES_PER_SPIKE} Joules.\n"
            "The energy used by each active FPGA per millisecond is "
            f"{MILLIWATTS_PER_FPGA} Joules.\n\n\n")

    def _write_fpga_cost(self, power_used, f):
        """
        FPGA cost model calculation.

        :param PowerUsed power_used: the runtime
        :param ~io.TextIOBase f: the file writer
        """
        version = get_config_int("Machine", "version")
        # if not spalloc, then could be any type of board
        if (not get_config_str("Machine", "spalloc_server") and
                not get_config_str("Machine", "remote_spinnaker_url")):
            # if a spinn2 or spinn3 (4 chip boards) then they have no fpgas
            if version in (2, 3):
                f.write(
                    f"A SpiNN-{version} board does not contain any FPGA's, "
                    f"and so its energy cost is 0 \n")
                return
            elif version not in (4, 5):
                # no idea where we are; version unrecognised
                raise ConfigurationException(
                    "Do not know what the FPGA setup is for this version of "
                    "SpiNNaker machine.")

            # if a spinn4 or spinn5 board, need to verify if wrap-arounds
            # are there, if not then assume fpgas are turned off.
            if power_used.num_fpgas == 0:
                # no active fpgas
                f.write(
                    f"The FPGA's on the SpiNN-{version} board are turned off "
                    f"and therefore the energy used by the FPGA is 0\n")
                return
            # active fpgas; fall through to shared main part report

        # print out as needed for spalloc and non-spalloc versions
        if version is None:
            f.write(
                f"{power_used.num_fpgas} FPGAs on the Spalloc-ed boards are "
                "turned on and therefore the energy used by the FPGA during "
                "the entire time the machine was booted (which was "
                f"{power_used.total_time_secs * 1000} ms) is "
                f"{power_used.fpga_total_energy_joules} Joules. "
                "The usage during execution was "
                f"{power_used.fpga_exec_energy_joules} Joules.")
        else:
            f.write(
                f"{power_used.num_fpgas} FPGA's on the SpiNN-{version} board "
                "are turned on and therefore the energy used by the FPGA "
                "during the entire time the machine was booted (which was "
                f"{power_used.total_time_secs * 1000} ms) is "
                f"{power_used.fpga_total_energy_joules} Joules. "
                "The usage during execution was "
                f"{power_used.fpga_exec_energy_joules} Joules.")

    @staticmethod
    def _write_chips_active_cost(
            chip_coord, labels, runtime_total_ms, power_used, f):
        """
        Figure out the chip active cost during simulation.

        :param tuple(int,int) chip_coord: the x,y of the chip to consider
        :param dict(int,str) labels: vertex labels for the active cores
        :param float runtime_total_ms:
        :param PowerUsed power_used:
        :param ~io.TextIOBase f: file writer
        :return: energy cost
        """
        (x, y) = chip_coord
        f.write("\n")

        # detailed report print out
        for core in range(Machine.DEFAULT_MAX_CORES_PER_CHIP):
            if core in labels:
                label = f" (running {labels[core]})"
            else:
                label = ""
            energy = power_used.get_core_active_energy_joules(x, y, core)
            f.write(
                f"processor {x}:{y}:{core}{label} used {energy} Joules by "
                "being active during the execution of the simulation\n")

        # TAKE INTO ACCOUNT IDLE COST
        idle_cost = runtime_total_ms * MILLIWATTS_PER_IDLE_CHIP

        f.write(
            f"The chip at {x},{y} used {idle_cost} Joules by "
            "being idle during the execution of the simulation\n")

    @staticmethod
    def _write_load_time_cost(power_used, f):
        """
        Energy usage from the loading phase.

        :param PowerUsed power_used:
        :param ~io.TextIOBase f: file writer
        """
        # find time in milliseconds
        with GlobalProvenance() as db:
            total_time_ms = db.get_timer_sum_by_category(TimerCategory.LOADING)

        # handle active routers etc
        active_router_cost = (
            power_used.loading_time_secs * 1000 * power_used.num_frames *
            MILLIWATTS_PER_FRAME_ACTIVE_COST)

        # detailed report write
        f.write(
            "The amount of time used during the loading process is "
            f"{total_time_ms} milliseconds.\nAssumed only 2 monitor cores is "
            "executing that this point. We also assume that there is a "
            "baseline active router/cooling component that is using "
            f"{active_router_cost} Joules. Overall the energy usage is "
            f"{power_used.loading_joules} Joules.\n")

    @staticmethod
    def _write_data_extraction_time_cost(power_used, f):
        """
        Data extraction cost.

        :param PowerUsed power_used:
        :param ~io.TextIOBase f: file writer
        """
        # find time
        with GlobalProvenance() as db:
            total_time_ms = db.get_timer_sum_by_algorithm(
                FecTimer.APPLICATION_RUNNER)

        # handle active routers etc
        energy_cost_of_active_router = (
            total_time_ms * power_used.num_frames *
            MILLIWATTS_PER_FRAME_ACTIVE_COST)

        # detailed report
        f.write(
            "The amount of time used during the data extraction process is "
            f"{total_time_ms} milliseconds.\nAssumed only 2 monitor cores is "
            "executing at this point. We also assume that there is a baseline "
            "active router/cooling component that is using "
            f"{energy_cost_of_active_router} Joules. Hence the overall energy "
            f"usage is {power_used.saving_joules} Joules.\n")
