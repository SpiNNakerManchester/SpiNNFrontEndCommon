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

from spinn_front_end_common.abstract_models import (
    AbstractHasAssociatedBinary)
from spinn_front_end_common.utilities.constants import SIMULATION_N_BYTES
from spinn_front_end_common.interface.ds import DataSpecificationGenerator
from spinn_front_end_common.interface.simulation.simulation_utilities import (
    get_simulation_header_array, get_simulation_header_array_no_timestep)

def generate_system_data_region(
        spec: DataSpecificationGenerator, region_id: int,
        machine_vertex: AbstractHasAssociatedBinary) -> None:
    """
    Generate a system data region for time-based simulations.

    :param spec: The data specification to write to
    :param region_id: The region to write to
    :param machine_vertex: The machine vertex to write for
    """
    # reserve memory regions
    spec.reserve_memory_region(
        region=region_id, size=SIMULATION_N_BYTES, label='systemInfo')

    # simulation .c requirements
    spec.switch_write_focus(region_id)
    spec.write_array(get_simulation_header_array(
        machine_vertex.get_binary_file_name()))


def generate_steps_system_data_region(
        spec: DataSpecificationGenerator, region_id: int,
        machine_vertex: AbstractHasAssociatedBinary) -> None:
    """
    Generate a system data region for step-based simulations.

    :param spec: The data specification to write to
    :param region_id: The region to write to
    :param machine_vertex: The machine vertex to write for
    """
    # reserve memory regions
    spec.reserve_memory_region(
        region=region_id, size=SIMULATION_N_BYTES, label='systemInfo')

    # simulation .c requirements
    spec.switch_write_focus(region_id)
    spec.write_array(get_simulation_header_array_no_timestep(
        machine_vertex.get_binary_file_name()))
