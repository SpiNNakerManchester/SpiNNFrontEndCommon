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

#: The simple properties of PowerUsed object to be reported
_BASIC_PROPERTIES = (
    # Counts
    "num_chips", "num_cores", "num_fpgas", "num_frames",
    # Times (in seconds)
    "total_time_secs", "booted_time_secs", "mapping_time_secs",
    "data_gen_time_secs", "loading_time_secs", "exec_time_secs",
    "saving_time_secs",
    # Energies (in Joules)
    "total_energy_joules", "baseline_joules",
    "fpga_total_energy_joules", "fpga_exec_energy_joules",
    "packet_joules", "mapping_joules", "data_gen_joules",
    "loading_joules", "chip_energy_joules", "saving_joules")
#: The main provenance key we use
_PROV_KEY = "power_provenance"


def energy_provenance_reporter(power_used):
    """
    Converts the power usage information into provenance data.

    :param PowerUsed power_used:
        The computed basic power consumption information
    """
    with ProvenanceWriter() as db:
        for prop in _BASIC_PROPERTIES:
            db.insert_power(
                __prop_name(prop), getattr(power_used, prop))
            for x, y, p in power_used.active_cores:
                db.insert_core(
                    x, y, p, "Energy (Joules)",
                    power_used.get_core_active_energy_joules(x, y, p))
            for x, y in power_used.active_routers:
                db.insert_router(
                    x, y, "Energy (Joules)",
                    power_used.get_router_active_energy_joules(x, y))


def __prop_name(name):
    name = name.capitalize()
    name = re.sub(r"_time_secs$", r" time (seconds)", name)
    return re.sub(r"(_energy)?_joules", r" energy (Joules)", name)


def __router_name(x, y):
    return f"router@{x},{y} energy (Joules)"
