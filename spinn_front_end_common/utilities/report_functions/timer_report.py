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
import sys
from spinn_utilities.config_holder import get_config_bool, get_config_float
from spinn_utilities.exceptions import SpiNNUtilsException
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance import (
    GlobalProvenance, TimerCategory, TimerWork)

logger = FormatAdapter(logging.getLogger(__name__))

#: converter between joules to kilowatt hours
JOULES_TO_KILOWATT_HOURS = 3600000

# report file name
TIMER_FILENAME = "timer_report.rpt"


def write_timer_report(
        report_path=None, database_file=None, timer_report_ratio=None,
        timer_report_ms=None, timer_report_to_stdout=None):
    """ Writes the timer report.

    Only provides parameters if using this standalone

    :param report_path: Where to write the report if not using the default
    :type report_path: None or str
    :param database_file: Where the provenance sqlite3 files is located if
        not using the default.
    :type database_file: None or str
    :param timer_report_ratio: Percentage of total time and algorithm must take
        to be shown. Or None to use cfg if available or default
    :type timer_report_ratio: None or float
    :param timer_report_ms: Time in ms which algorithm must take
        to be shown. Or None to use cfg if available or default
    :type timer_report_ms: None or float
    :param timer_report_to_stdout:
        Flag to say output should go to the terminal.
        Or None to use cfg if available or default
    :rtype: None
    """
    if report_path is None:
        try:
            report_path = timer_report_file()
        except SpiNNUtilsException:
            report_path = os.path.join(os.path.curdir, TIMER_FILENAME)
            logger.warning(f"no report_path so writing to {report_path}")

    # create report
    if timer_report_to_stdout is None:
        try:
            timer_report_to_stdout = get_config_bool(
                "Reports", "timer_report_to_stdout")
        except Exception:
            logger.warning("No timer_report_to_stdout found so using False")
            timer_report_to_stdout = False

    with GlobalProvenance(
            database_file=database_file, read_only=True) as reader:
        if timer_report_to_stdout:
            __write_timer_report(
                sys.stdout, reader, timer_report_ratio, timer_report_ms)
        else:
            with open(report_path, "w", encoding="utf-8") as f:
                __write_timer_report(
                    f, reader, timer_report_ratio, timer_report_ms)


def timer_report_file():
    report_dir = FecDataView.get_timestamp_dir_path()
    return os.path.join(report_dir, TIMER_FILENAME)


def __write_timer_report(f, reader, timer_report_ratio, timer_report_ms):
    """ Write time report into the file

    :param ~io.TextIOBase f: file writer
    :param ProvenanceReader reader:
    :type timer_report_ratio: None or float
    :type timer_report_ms: None or float
    """
    f.write("Summary timer report\n-------------------\n\n")

    total = __report_category_sums(f, reader)
    __report_works_sums(f, reader)
    __report_algorithms(
        f, reader, total, timer_report_ratio, timer_report_ms)


def __report_category_sums(f, reader):
    """

     :param ~io.TextIOBase f: file writer
     :param ProvenanceReader reader:
     """
    total_on = 0
    total_off = 0
    f.write("category_name                  time_on     time_off\n")
    for category in TimerCategory:
        on, off = reader.get_category_timer_sums(category)
        total_on += on
        total_off += off
        f.write(f"{category.category_name:18} {on:10.3f}ms {off:10.3f}ms \n")
    f.write(f"\nIn total the script took {(total_on + total_off):10.2f} "
            f"of which the machine was on for {total_on:10.2f}\n\n")
    return total_on + total_off


def __report_works_sums(f, reader):
    """

     :param ~io.TextIOBase f: file writer
     :param ProvenanceReader reader:
     """
    f.write("work type         time\n")
    for work in TimerWork:
        time = reader.get_timer_sum_by_work(work)
        f.write(f"{work.work_name:18} {time:10.3f}ms\n")
    f.write("\n\n")


def __report_algorithms(
        f, reader, total, timer_report_ratio, timer_report_ms):
    """ Write time report into the file

    :param ~io.TextIOBase f: file writer
    :param ProvenanceReader reader:
    :param float total:
    :type timer_report_ratio: None or float
    :type timer_report_ms: None or float
    """
    if timer_report_ratio is None:
        try:
            timer_report_ratio = get_config_float(
                "Reports", "timer_report_ratio")
        except Exception:
            logger.warning("No timer_report_ratio so using 1%")
            timer_report_ratio = 0.01

    if timer_report_ms is None:
        try:
            timer_report_ms = get_config_float(
                "Reports", "timer_report_ms")
        except Exception:
            logger.warning("No timer_report_ms so using 10ms")
            timer_report_ms = 1000

    cutoff = total * timer_report_ratio
    if cutoff < timer_report_ms:
        f.write(f"algorithms which ran for longer than {timer_report_ratio}"
                f" of the total time\n")
    else:
        cutoff = timer_report_ms
        f.write(f"algorithms which ran for longer than {cutoff}ms\n")
    data = reader.get_all_timer_provenance()
    f.write("Name                       total_time n_runs\n")
    for name, time, count in data:
        if time > cutoff:
            f.write(f"{name:35} {time:10.3f} {count}\n")
    f.write("\n\n")
