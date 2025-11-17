# Copyright (c) 2025 The University of Manchester
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
from typing import Optional
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.sqlite_db import SQLiteDB


class DatabaseUpdater(SQLiteDB):
    """
    A reader for the database.
    """
    __slots__ = ()

    def __init__(self, database_path: str):
        """
        :param database_path: The path to the database
        """
        super().__init__(database_path, read_only=False, text_factory=str)

    def update_system_params(self, runtime: Optional[float]) -> None:
        """
        Write system parameters into the database.
        """
        self.cursor().executemany(
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
