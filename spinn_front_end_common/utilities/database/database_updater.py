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
from spinn_utilities.log import FormatAdapter
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB

logger = FormatAdapter(logging.getLogger(__name__))


class DatabaseUpdater(SQLiteDB):
    """
    The interface for the database system for main front ends.
    Any special tables needed from a front end should be done
    by subclasses of this interface.
    """

    __slots__ = [
    ]

    def add_system_params(self, runtime):
        """
        Write system parameters into the database.

        :param int runtime: the amount of time the application is to run for
        """
        with self.transaction() as cur:
            cur.executemany(
                """
                INSERT OR REPLACE INTO configuration_parameters (
                    parameter_id, value)
                VALUES (?, ?)
                """, [
                    ("machine_time_step",
                     FecDataView.get_simulation_time_step_us()),
                    ("time_scale_factor",
                     FecDataView.get_time_scale_factor()),
                    ("infinite_run", str(runtime is None)),
                    ("runtime", -1 if runtime is None else runtime),
                    ("app_id", FecDataView.get_app_id())])
