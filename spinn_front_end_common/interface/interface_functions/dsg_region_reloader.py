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
import numpy
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.interface.ds import (
    DataSpecificationReloader, DsSqlliteDatabase)
from spinn_front_end_common.utilities.helpful_functions import (
    get_region_base_address_offset)
from spinn_front_end_common.utilities.utility_calls import get_report_writer
from spinn_front_end_common.abstract_models import (
    AbstractRewritesDataSpecification)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.helpful_functions import (
    generate_unique_folder_name)
from spinn_front_end_common.utilities.constants import BYTES_PER_WORD


def reload_dsg_regions():
    """
    Reloads DSG regions where needed.
    """
    progress = ProgressBar(
        FecDataView.get_n_placements(), "Reloading data")
    for placement in progress.over(FecDataView.iterate_placemements()):
        # Generate the data spec for the placement if needed
        regenerate_data_spec(placement, FecDataView.get_dsg_targets())


def get_reload_data_dir():
    """
    Get a path in which reloaded data files can be written.

    :rtype: str
    """
    run_dir_path = FecDataView.get_run_dir_path()
    data_dir = generate_unique_folder_name(
        run_dir_path, "reloaded_data_regions", "")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return data_dir


def regenerate_data_spec(placement, ds_db):
    """
    Regenerate a data specification for a placement.

    :param ~.Placement placement: The placement to regenerate
    :param DsSqlliteDatabase ds_db: Database used in original DS load
    :return: Whether the data was regenerated or not
    :rtype: bool
    """
    vertex = placement.vertex

    # If the vertex doesn't regenerate, skip
    if not isinstance(vertex, AbstractRewritesDataSpecification):
        return False

    # If the vertex doesn't require regeneration, skip
    if not vertex.reload_required():
        return False

    report_writer = get_report_writer(
        placement.x, placement.y, placement.p, True)

    # build the file writer for the spec
    reloader = DataSpecificationReloader(
        placement.x, placement.y, placement.p, ds_db, report_writer)

    # Execute the regeneration
    vertex.regenerate_data_specification(reloader, placement)

    vertex.set_reload_required(False)
    return True


def _get_ptr_table(txrx, placement, regions_base_address, start_region):
    """
    Read the pointer table.

    :param ~spinnman.transceiver.Transceiver txrx:
        The transceiver to read with
    :param ~pacman.model.placements.Placement placement:
        Where to read the pointer table from
    :param int regions_base_address: The start of memory for the given core
    :param int start_region: The address of the first region address
    :rtype: ~numpy.ndarray(
        ~data_specification.DataSpecificationExecutor.TABLE_TYPE)
    """
    # Read the pointer table from the machine
    table_size = get_region_base_address_offset(
        regions_base_address, MAX_MEM_REGIONS) - start_region
    ptr_table = numpy.frombuffer(txrx.read_memory(
            placement.x, placement.y, start_region, table_size),
        dtype=DataSpecificationExecutor.TABLE_TYPE)

    # Fill in the size of regions which have no size but which are valid
    fixed_ptr_table = numpy.zeros(
        MAX_MEM_REGIONS, dtype=DataSpecificationExecutor.TABLE_TYPE)
    fixed_ptr_table[:] = ptr_table[:]
    last_no_size_region = None
    for i in range(0, MAX_MEM_REGIONS):

        # If this region is a valid region
        if ptr_table[i]["pointer"] != 0:

            # If there is a previous region with no size, use this region
            # pointer to find the size of the last one
            if last_no_size_region is not None:
                fixed_ptr_table[last_no_size_region]["n_words"] = (
                    ptr_table[i]["pointer"] -
                    ptr_table[last_no_size_region]["pointer"]) / BYTES_PER_WORD
                last_no_size_region = None

            # If this region has no size, make it the next to find the size of
            if ptr_table[i]["n_words"] == 0:
                last_no_size_region = i

    # We can get here and have the last region have no size; this is hard
    # to fix since we don't know where the data for the next region is!
    if last_no_size_region is not None:
        fixed_ptr_table[last_no_size_region]["n_words"] = -1
    return fixed_ptr_table
