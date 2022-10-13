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
from spinn_utilities.config_holder import get_config_float
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance import (
    ProvenanceReader, TimerCategory, TimerWork)

logger = FormatAdapter(logging.getLogger(__name__))

#: converter between joules to kilowatt hours
JOULES_TO_KILOWATT_HOURS = 3600000

# report file name
TIMER_FILENAME = "timer_report.rpt"

def write_timer_report(
        report_path=None, provenance_path=None, algorithm_report_percent=None,
        algorithm_report_ms=None):
    """ Writes the timer report.

    Only provides parameters if using this standalone

    :param report_path: Where to write the report if not using the default
    :type report_path: None or str
    :param provenance_path: Where the provenance sqlite3 files is located if
        not using the default.
    :type provenance_path: None or str
    :param algorithm_report_percent: Percentage of total time and algorithm must take
    to be shown. Or None to use cfg if available or default
    :type algorithm_report_percent; None or float
    :param algorithm_report_ms: Time in ms which algorithm must take
    to be shown. Or None to use cfg if available or default
    :type algorithm_report_ms: None or float

    =None, cutoff_value

    :rtype: None
    """
    if report_path is None:
        run_dir = FecDataView.get_run_dir_path()
        if not run_dir.endswith("run_1"):
            logger.warning(
                "timer report does not currently work well after a reset")
        report_path = os.path.join(run_dir, TIMER_FILENAME)

    # create report
    reader = ProvenanceReader(provenance_data_path=provenance_path)
    with open(report_path, "w", encoding="utf-8") as f:
        __write_timer_report(
            f, reader, algorithm_report_percent, algorithm_report_ms)


def __write_timer_report(f, reader, algorithm_report_percent, algorithm_report_ms):
    """ Write time report into the file

    :param ~io.TextIOBase f: file writer
    :param ProvenanceReader reader:
    """
    f.write("Summary timer report\n-------------------\n\n")

    total = __report_category_sums(f, reader)
    __report_works_sums(f, reader)
    __report_algorithms(
        f, reader, total, algorithm_report_percent, algorithm_report_ms)


def __report_category_sums(f, reader):
    total_on = 0
    total_off = 0
    f.write(f"category_name         time_on     time_off\n")
    for category in TimerCategory:
        on, off = reader.get_category_timer_sums(category)
        total_on += on
        total_off += off
        f.write(f"{category.category_name:18} {on:10.3f}ms {off:10.3f}ms \n")
    f.write(f"\nIn total the script took {(total_on + total_off):10.2f} "
            f"of which the machine was on for {total_on:10.2f}\n\n")
    return total_on + total_off


def __report_works_sums(f, reader):
    f.write(f"work type         time\n")
    for work in TimerWork:
        time = reader.get_timer_sum_by_work(work)
        f.write(f"{work.work_name:18} {time:10.3f}ms\n")
    f.write(f"\n\n")


def __report_algorithms(
        f, reader, total, algorithm_report_ratio, algorithm_report_ms):
    if algorithm_report_ratio is None:
        try:
            algorithm_report_ratio = get_config_float(
                "report", "algorithm_report_percent")
        except Exception:
            logger.warning("No algorithm_report_ratio so using 1%")
            algorithm_report_ratio = 0.01

    if algorithm_report_ms is None:
        try:
            algorithm_report_ms = get_config_float(
                "report", "algorithm_report_ms")
        except Exception:
            logger.warning("No algorithm_report_ms so using 10ms")
            algorithm_report_ms = 10

    cutoff = total * algorithm_report_ratio
    if cutoff < algorithm_report_ms:
        f.write(f"algorithms which ran for longer than {algorithm_report_ratio}"
                f" of the total time\n")
    else:
        cutoff = algorithm_report_ms
        f.write(f"algorithms which ran for longer than {cutoff}ms\n")
    data = reader.get_all_timer_provenance()
    f.write(f"algorithms which ran for longer than {cutoff}ms\n")
    f.write("Name  total_time n_runs\n")
    for name, time, count in data:
        if time > cutoff:
            f.write(f"{name:35} {time:10.3f} {count}\n")
    f.write(f"\n\n")
