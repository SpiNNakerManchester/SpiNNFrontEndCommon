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

import os
from spinn_front_end_common.data import FecDataView

_REPORT_FILENAME = "tags_on_machine.txt"


def tags_from_machine_report():
    """
    Describes what the tags actually present on the machine are.
    """
    filename = os.path.join(FecDataView.get_run_dir_path(), _REPORT_FILENAME)
    tags = _get_tags()
    with open(filename, "w", encoding="utf-8") as f:
        f.write("Tags actually read off the machine\n")
        f.write("==================================\n")
        for tag in tags:
            f.write(f"{repr(tag)}\n")


def _get_tags():
    try:
        return FecDataView.get_transceiver().get_tags()
    except Exception as e:  # pylint: disable=broad-except
        return [e]
