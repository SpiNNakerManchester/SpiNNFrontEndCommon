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

from collections import defaultdict
import logging
import numpy
import os
from spinn_utilities.config_holder import (get_config_int, get_config_str)
from spinn_utilities.exceptions import SpiNNUtilsException
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.buffer_management.storage_objects \
    import (SqlLiteDatabase)
from spinn_front_end_common.interface.provenance import (
    FecTimer, ProvenanceReader, TimerCategory)
from spinn_front_end_common.utility_models import ChipPowerMonitorMachineVertex
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.interface.interface_functions.compute_energy_used\
    import (JOULES_PER_SPIKE, MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD,
            MILLIWATTS_PER_FRAME_ACTIVE_COST, MILLIWATTS_PER_FPGA,
            MILLIWATTS_PER_IDLE_CHIP)
from spinn_machine.machine import Machine

logger = FormatAdapter(logging.getLogger(__name__))

#: converter between joules to kilowatt hours
JOULES_TO_KILOWATT_HOURS = 3600000

# energy report file name
CHIP_ACTIVE_FILENAME = "chip_active_report.rpt"

def write_chip_active_report(report_path=None, buffer_path=None):
    """ Writes the report.

    :param report_path: Where to write the report if not using the default
    :type report_path: None or str
    :param buffer_path: Where the provenance sqlite3 files is located
        if not using the default.
    :type buffer_path: None or str
    :rtype: None
    """
    if report_path is None:
        try:
            report_dir = FecDataView.get_run_dir_path()
            report_path = os.path.join(
                report_dir, CHIP_ACTIVE_FILENAME)
        except SpiNNUtilsException:
            report_path = os.path.join(
                os.path.curdir, CHIP_ACTIVE_FILENAME)
            logger.warning(f"no report_path so writing to {report_path}")

    # create detailed report
    with open(report_path, "w", encoding="utf-8") as f:
        __write_report(f, buffer_path)

def __write_report(f, buffer_path):
    db = SqlLiteDatabase(buffer_path)
    n_samples_per_recording = get_config_int(
        "EnergyMonitor", "n_samples_per_recording_entry")

    for row in db.iterate_chip_power_monitor_cores():
        record_raw, data_missing = db.get_region_data(
            row["x"], row["y"], row["processor"], 0)
        results = (
            numpy.frombuffer(record_raw, dtype="uint32").reshape(-1, 18) /
            n_samples_per_recording)
        active_sums = numpy.sum(results, axis=0)
        activity_count = numpy.sum(results)
        time_for_recorded_sample =\
            (row["sampling_frequency"] * n_samples_per_recording) / 1000

        for core in range(0, 18):
            label = db.get_label(row["x"], row["y"], core)
            if (active_sums[core] > 0) or label:
                energy = (active_sums[core] * time_for_recorded_sample *
                            MILLIWATTS_PER_CHIP_ACTIVE_OVERHEAD / 18)
                f.write(
                    f"processor {row['x']}:{row['y']}:{core}({label})"
                    f" was active for {active_sums[core]} "
                    f" using {energy} Joules\n")
