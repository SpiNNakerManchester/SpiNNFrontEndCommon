# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import traceback
from spinn_utilities.log import FormatAdapter
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.interface.provenance import (
    AbstractProvidesProvenanceDataFromMachine, ProvenanceWriter)

logger = FormatAdapter(logging.getLogger(__name__))


def placements_provenance_gatherer(n_placements, placements):
    """ Gets provenance information from placements

    :param int n_placements: Number of placements to gather
    :param iterator(Placement) placements:
        The placements of the vertices to gather data form.
        May not be all placements so dont use View
    :return:
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
            with ProvenanceWriter() as db:
                db.add_core_name(placement.x, placement.y, placement.p,
                                 placement.vertex.label)

        except Exception:  # pylint: disable=broad-except
            errors.append(traceback.format_exc())
