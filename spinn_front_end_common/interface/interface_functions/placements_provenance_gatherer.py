# Copyright (c) 2016 The University of Manchester
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
import traceback
from spinn_utilities.log import FormatAdapter
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.interface.provenance import (
    AbstractProvidesProvenanceDataFromMachine)

logger = FormatAdapter(logging.getLogger(__name__))


def placements_provenance_gatherer(n_placements, placements):
    """
    Gets provenance information from placements.

    :param int n_placements: Number of placements to gather
    :param iterator(~pacman.model.placements.Placement) placements:
        The placements of the vertices to gather data form.
        May not be all placements so don't use View
    """
    errors = list()

    progress = ProgressBar(n_placements, "Getting provenance data")

    # retrieve provenance data from any cores that provide data
    for placement in progress.over(placements):
        _add_placement_provenance(placement, errors)
    if errors:
        logger.warning("Errors found during provenance gathering:")
        for error in errors:
            logger.warning("{}", error)


def _add_placement_provenance(placement, errors):
    """
    :param ~.Placement placement:
    :param list(str) errors:
    """
    # retrieve provenance data from any cores that provide data
    if isinstance(
            placement.vertex, AbstractProvidesProvenanceDataFromMachine):
        # get data
        try:
            placement.vertex.get_provenance_data_from_machine(placement)

        except Exception:  # pylint: disable=broad-except
            errors.append(traceback.format_exc())
