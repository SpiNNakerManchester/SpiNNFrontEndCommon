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

import re
from spinn_front_end_common.interface.provenance import ProvenanceWriter
from spinn_front_end_common.utilities.utility_objs import PowerUsed

#: The simple properties of PowerUsed object to be reported
_BASIC_PROPERTIES = (
    # Counts
    "n_chips", "n_cores", "n_boards", "n_frames",
    # Times (in seconds)
    "exec_time_s", "mapping_time_s", "loading_time_s",
    "saving_time_s", "other_time_s",
    # Energies (in Joules)
    "exec_energy_j", "mapping_energy_j", "loading_energy_j",
    "saving_energy_j", "other_energy_j")
#: The main provenance key we use
_PROV_KEY = "power_provenance"


def energy_provenance_reporter(power_used: PowerUsed) -> None:
    """
    Converts the power usage information into provenance data.

    :param power_used:
        The computed basic power consumption information
    """
    with ProvenanceWriter() as db:
        for prop in _BASIC_PROPERTIES:
            db.insert_power(
                __prop_name(prop), getattr(power_used, prop))


def __prop_name(name: str) -> str:
    name = name.capitalize()
    name = re.sub(r"_time_s$", r" time (seconds)", name)
    return re.sub(r"_energy_j$", r" energy (Joules)", name)
