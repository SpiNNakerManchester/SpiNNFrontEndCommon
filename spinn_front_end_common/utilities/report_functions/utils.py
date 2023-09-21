# Copyright (c) 2023 The University of Manchester
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

from contextlib import contextmanager
import csv


@contextmanager
def csvopen(filename, header, *, mode="w"):
    """
    Open a CSV file for writing, write a header row (comma-separated string),
    and yield a writer for the CSV rows.

    Intended to be used like this::

        with csvopen("abc.csv", "A,B,C") as csv:
            csv.writerow([1,2,3])

    .. note::
        This handles all the complexities of quoting so you can ignore them.
    """
    with open(filename, mode, encoding="utf-8", newline="") as f:
        at_start = f.tell() == 0
        csv_writer = csv.writer(f)
        if header is not None and at_start:
            csv_writer.writerow(header.split(","))
        yield csv_writer
