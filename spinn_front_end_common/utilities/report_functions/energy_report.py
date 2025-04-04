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

import logging
import os
from typing import TextIO
from spinn_utilities.config_holder import get_config_str
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.utility_objs import PowerUsed

logger = FormatAdapter(logging.getLogger(__name__))


class EnergyReport(object):
    """
    This class creates a report about the approximate total energy
    consumed by a SpiNNaker job execution.
    """

    __slots__ = ()

    @classmethod
    def file_name(cls, n_run: int) -> str:
        """ Name of the Energy report file for this run """
        path = get_config_str("Reports", "path_energy_report")
        assert "{n_run}" in path,\
            "cfg value: path_energy_report needs to include {n_run}"
        return path.replace("{n_run}", str(n_run))

    def write_energy_report(self, power_used: PowerUsed) -> None:
        """
        Writes the report.

        :param ~spinn_machine.Machine machine: the machine
        :param PowerUsed power_used:
        """
        report_dir = FecDataView.get_run_dir_path()

        # summary report path
        summary_report = os.path.join(
            report_dir, self.file_name(FecDataView.get_run_number()))

        # create summary report
        with open(summary_report, "w", encoding="utf-8") as f:
            self._write_summary_report(f, power_used)

    @classmethod
    def _write_summary_report(cls, f: TextIO, power_used: PowerUsed) -> None:
        """
        Write summary file.

        :param ~io.TextIOBase f: file writer
        :param PowerUsed power_used:
        """
        f.write("Energy Report\n")
        f.write("=============\n")
        f.write(f"Simulation used {power_used.n_boards} boards, "
                f"in {power_used.n_frames} frames "
                f"made up of {power_used.n_chips} chips\n")
        f.write(f"Simulation cores used: {power_used.n_cores} in total, "
                f"{power_used.n_active_cores} actively on "
                f"{power_used.n_active_chips} chips\n\n")
        f.write(f"Simulation execution time: {power_used.exec_time_s} "
                "seconds\n")
        f.write(f"Simulation execution energy: {power_used.exec_energy_j}"
                " Joules\n\n")
        f.write(f"Simulation execution energy (active chips and cores only): "
                f"{power_used.exec_energy_cores_j} Joules\n")
        f.write(f"Simulation execution energy (ignoring frame power): "
                f"{power_used.exec_energy_boards_j} Joules\n\n")
        f.write(f"Mapping time: {power_used.mapping_time_s} seconds\n")
        f.write(f"Mapping energy: {power_used.mapping_energy_j} Joules\n\n")

        f.write(f"Loading time: {power_used.loading_time_s} seconds\n")
        f.write(f"Loading energy: {power_used.loading_energy_j} Joules\n\n")

        f.write(f"Saving time: {power_used.saving_time_s} seconds\n")
        f.write(f"Saving energy: {power_used.saving_energy_j} Joules\n\n")

        f.write(f"Other time: {power_used.other_time_s} seconds\n")
        f.write(f"Other energy: {power_used.other_energy_j} Joules\n\n")

        f.write(f"Total energy: {power_used.total_energy_j} Joules\n")
