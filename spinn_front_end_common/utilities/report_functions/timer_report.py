# Copyright (c) 2017 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
        timer_report_to_stdout = get_config_bool(
            "Reports", "timer_report_to_stdout")

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

    len_name, len_time, len_runs = __get_sizes(reader)
    total = __report_category_sums(f, reader, len_name, len_time)
    __report_works_sums(f, reader, total, len_name, len_time)
    __report_algorithms(
        f, reader, total, timer_report_ratio, timer_report_ms,
        len_name, len_time, len_runs)


def __get_sizes(reader):
    len_name = 0
    max_time = 0
    max_runs = 0
    for category in TimerCategory:
        on, off = reader.get_category_timer_sums(category)
        max_time = max(max_time, on, off)
        len_name = max(len_name, len(category.category_name))
    for work in TimerWork:
        time = reader.get_timer_sum_by_work(work)
        max_time = max(max_time, time)
        len_name = max(len_name, len(work.work_name))
    data = reader.get_all_timer_provenance()
    for name, time, runs in data:
        max_time = max(max_time, time)
        len_name = max(len_name, len(name))
        max_runs = max(max_runs, runs)
    time_st = f"{max_time:.3f}"
    run_st = f"{max_runs:d}"
    return len_name, len(time_st), len(run_st)


def __report_category_sums(f, reader, len_name, len_time):
    """
     :param ~io.TextIOBase f: file writer
     :param ProvenanceReader reader:
     """
    total_on = 0
    total_off = 0
    f.write(f"{'category_name':{len_name}}   {'time_on':>{len_time}}   "
            f"time_off{len_time}>\n")
    for category in TimerCategory:
        on, off = reader.get_category_timer_sums(category)
        total_on += on
        total_off += off
        f.write(f"{category.category_name:{len_name}} {on:{len_time}.3f}ms "
                f"{off:{len_time}.3f}ms \n")
    f.write(f"\nIn total the script took {(total_on + total_off):10.2f}ms "
            f"of which the machine was on for {total_on:10.2f}ms\n\n")
    return total_on + total_off


def __report_works_sums(f, reader, total, len_name, len_time):
    """

     :param ~io.TextIOBase f: file writer
     :param ProvenanceReader reader:
     """
    work_total = 0
    f.write(f"{'work type':{len_name}}   {'time':>{len_time}}\n")
    for work in TimerWork:
        time = reader.get_timer_sum_by_work(work)
        work_total += time
        f.write(f"{work.work_name:{len_name}} {time:{len_time}.3f}ms\n")
    if work_total < total:
        f.write(f"{'Outside of Algorithms':{len_name}} "
                f"{(total-work_total):{len_time}.3f}ms\n")
    f.write("\n\n")


def __report_algorithms(
        f, reader, total, timer_report_ratio, timer_report_ms,
        len_name, len_time, len_runs):
    """ Write time report into the file

    :param ~io.TextIOBase f: file writer
    :param ProvenanceReader reader:
    :param float total:
    :type timer_report_ratio: None or float
    :type timer_report_ms: None or float
    """
    if timer_report_ratio is None:
        timer_report_ratio = get_config_float("Reports", "timer_report_ratio")

    if timer_report_ms is None:
        timer_report_ms = get_config_float("Reports", "timer_report_ms")

    cutoff = total * timer_report_ratio
    if cutoff < timer_report_ms:
        f.write(f"algorithms which ran for longer than {timer_report_ratio}"
                f" of the total time\n")
    else:
        cutoff = timer_report_ms
        f.write(f"algorithms which ran for longer than {cutoff}ms\n")
    data = reader.get_all_timer_provenance()
    if len_time >= 8:
        f.write(f"{'Name':{len_name}}   {'total_time':>{len_time}} n_runs\n")
    else:
        cat_len = len_name - 10
        f.write(f"{'Name':{cat_len}} total_time n_runs\n")
    for name, time, count in data:
        if time > cutoff:
            f.write(f"{name:{len_name}} {time:{len_time}.3f}ms     "
                    f"{count:{len_runs}d}\n")
    f.write("\n\n")
