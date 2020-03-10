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
import pandas as pd

logger = logging.getLogger(__name__)


class PlacementsProvenanceGatherer(object):
    __slots__ = []

    def __call__(self, transceiver, placements):
        """
        :param transceiver: the SpiNNMan interface object
        :param placements: The placements of the vertices
        """

        prov_items = list()
        prov_placement = list()

        progress = ProgressBar(
            placements.n_placements, "Getting provenance data")

        # retrieve provenance data from any cores that provide data
        for placement in progress.over(placements.placements):
            if isinstance(placement.vertex,
                          AbstractProvidesProvenanceDataFromMachine):
                # get data
                new_prov = placement.vertex.get_provenance_data_from_machine(
                    transceiver, placement)
                prov_items.extend(
                    new_prov
                    )
                prov_placement.extend([placement]*len(new_prov))

        # write provenance to file here in a useful way
        columns = ['pop', 'label', 'min_atom', 'max_atom', 'no_atoms',
                   'x', 'y', 'p',
                   'prov_name', 'prov_value',
                   'fixed_sdram', 'sdram_per_timestep',
                   'cpu_cycles', 'dtcm']
        assert (len(prov_placement) == len(prov_items))
        structured_provenance = list()
        for i, (provenance, placement) in enumerate(zip(prov_items, prov_placement)):
            prov_name = provenance.names[1]
            prov_value = provenance.value
            pop = placement.vertex.label.split(":")[0]
            x = placement.x
            y = placement.y
            p = placement.p
            fixed_sdram = placement.vertex.resources_required.sdram.fixed
            sdram_per_timestep = placement.vertex.resources_required.sdram.per_timestep
            cpu_cycles = placement.vertex.resources_required.cpu_cycles.get_value()
            dtcm = placement.vertex.resources_required.dtcm.get_value()

            label = placement.vertex.label
            slices = label.split(":")
            max_atom = int(slices[-1])
            min_atom = int(slices[-2])
            no_atoms = max_atom - min_atom + 1

            structured_provenance.append(
                [pop, label, min_atom, max_atom, no_atoms,
                 x, y, p,
                 prov_name, prov_value,
                 fixed_sdram, sdram_per_timestep,
                 cpu_cycles, dtcm]
            )

        structured_provenance_df = pd.DataFrame.from_records(
            structured_provenance, columns=columns)
        structured_provenance_df.to_csv("structured_provenance.csv")

        return prov_items
