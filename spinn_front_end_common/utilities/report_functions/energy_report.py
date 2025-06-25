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
from typing import TextIO

from spinn_utilities.config_holder import get_report_path
from spinn_utilities.log import FormatAdapter

from spinn_front_end_common.utilities.utility_objs import PowerUsed

logger = FormatAdapter(logging.getLogger(__name__))


class EnergyReport(object):
    """
    This class creates a report about the approximate total energy
    consumed by a SpiNNaker job execution.
    """

    __slots__ = ()

    def write_energy_report(self, power_used: PowerUsed) -> None:
        """
        Writes the report.

        :param power_used:
        """
        # summary report path
        summary_report = get_report_path("path_energy_report")

        # create summary report
        with open(summary_report, "w", encoding="utf-8") as f:
            self._write_summary_report(f, power_used)

    @classmethod
    def _write_summary_report(cls, f: TextIO, power_used: PowerUsed) -> None:
        """
        Write summary file.

        :param f: file writer
        :param power_used:
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
