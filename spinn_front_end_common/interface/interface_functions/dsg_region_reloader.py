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

from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.interface.ds import (
    DsSqlliteDatabase, DataSpecificationReloader)
from spinn_front_end_common.utilities.utility_calls import get_report_writer
from spinn_front_end_common.abstract_models import (
    AbstractRewritesDataSpecification)
from spinn_front_end_common.data import FecDataView


def reload_dsg_regions():
    """
    Reloads DSG regions where needed.
    """
    progress = ProgressBar(
        FecDataView.get_n_placements(), "Reloading data")
    with DsSqlliteDatabase() as ds_database:
        for placement in progress.over(FecDataView.iterate_placemements()):
            # Generate the data spec for the placement if needed
            regenerate_data_spec(placement, ds_database)


def regenerate_data_spec(placement, ds_database):
    """
    Regenerate a data specification for a placement.

    :param ~.Placement placement: The placement to regenerate
    :param ds_database: The database to use for reload
    :type ds_database: ~spinn_front_end_common.interface.ds.DsSqlliteDatabas db
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
        placement.x, placement.y, placement.p, ds_database, report_writer)

    # Execute the regeneration
    vertex.regenerate_data_specification(reloader, placement)

    vertex.set_reload_required(False)
    return True
