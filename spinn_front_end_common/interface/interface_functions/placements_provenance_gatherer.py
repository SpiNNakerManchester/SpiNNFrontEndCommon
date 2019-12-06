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
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.interface.provenance import (
    AbstractProvidesProvenanceDataFromMachine)

logger = logging.getLogger(__name__)


class PlacementsProvenanceGatherer(object):
    __slots__ = []

    def __call__(self, transceiver, placements):
        """
        :param transceiver: the SpiNNMan interface object
        :param placements: The placements of the vertices
        """

        prov_items = list()

        progress = ProgressBar(
            placements.n_placements, "Getting provenance data")

        # retrieve provenance data from any cores that provide data
        for placement in progress.over(placements.placements):
            if isinstance(placement.vertex,
                          AbstractProvidesProvenanceDataFromMachine):
                # get data
                prov_items.extend(
                    placement.vertex.get_provenance_data_from_machine(
                        transceiver, placement))

        return prov_items
