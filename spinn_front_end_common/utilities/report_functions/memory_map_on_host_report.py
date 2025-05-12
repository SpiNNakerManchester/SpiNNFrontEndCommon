# Copyright (c) 2015 The University of Manchester
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

from spinn_utilities.config_holder import get_report_path
from spinn_utilities.log import FormatAdapter

from spinn_front_end_common.interface.ds import DsSqlliteDatabase

logger = FormatAdapter(logging.getLogger(__name__))


def memory_map_on_host_report() -> None:
    """
    Report on memory usage.
    """
    file_name = get_report_path("path_memory_map_report_map")
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            f.write("On host data specification executor\n")
            with DsSqlliteDatabase() as ds_database:
                for xyp, start_address, memory_used, memory_written in \
                        ds_database.get_info_for_cores():
                    f.write(
                        f"{xyp}: ('start_address': {start_address}, "
                        f"hex:{hex(start_address)}), "
                        f"'memory_used': {memory_used}, "
                        f"'memory_written': {memory_written}\n")
    except IOError:
        logger.exception("Generate_placement_reports: Can't open file"
                         " {} for writing.", file_name)
