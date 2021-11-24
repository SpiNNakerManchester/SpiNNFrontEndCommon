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

import pandas as pd
import numpy as np
import os
import logging
import traceback
from spinn_utilities.log import FormatAdapter
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.interface.provenance import (
    AbstractProvidesProvenanceDataFromMachine, ProvenanceWriter)
from spinn_front_end_common.utilities.globals_variables import get_simulator

logger = FormatAdapter(logging.getLogger(__name__))


def placements_provenance_gatherer(transceiver, placements):
    """ Gets provenance information from vertices on the machine.

    :param ~spinnman.transceiver.Transceiver transceiver:
        the SpiNNMan interface object
    :param ~pacman.model.placements.Placements placements:
        The placements of the vertices
    """
    errors = list()

    progress = ProgressBar(
        placements.n_placements, "Getting provenance data")

    # retrieve provenance data from any cores that provide data
    for placement in progress.over(placements.placements):
        _add_placement_provenance(placement, transceiver, errors)
    if errors:
        logger.warning("Errors found during provenance gathering:")
        for error in errors:
            logger.warning("{}", error)

    # Custom provenance presentation from SpiNNCer
    # write provenance to file here in a useful way
    columns = ['pop', 'label', 'min_atom', 'max_atom', 'no_atoms',
               'x', 'y', 'p',
               'prov_name', 'prov_value',
               'fixed_sdram', 'sdram_per_timestep',
               'cpu_cycles', 'dtcm']
    assert (len(prov_placement) == len(prov_items))
    structured_provenance = list()
    metadata = {}
    simulator = get_simulator()
    # Retrieve filename from spynnaker8/spinnaker.py
    provenance_filename = simulator.structured_provenance_filename

    if provenance_filename:
        # Produce metadata from the simulator info
        metadata['name'] = simulator.name
        metadata['no_machine_time_steps'] = simulator.no_machine_time_steps
        metadata['machine_time_step'] = simulator.machine_time_step
        metadata['config'] = simulator.config
        metadata['machine'] = simulator.machine
        metadata['structured_provenance_filename'] = simulator.\
            structured_provenance_filename

        for i, (provenance, placement) in enumerate(
                zip(prov_items, prov_placement)):
            prov_name = provenance.names[1]
            prov_value = provenance.value
            pop = placement.vertex.label.split(":")[0]
            x = placement.x
            y = placement.y
            p = placement.p
            fixed_sdram = placement.vertex.resources_required.sdram.fixed
            sdram_per_timestep = placement.vertex.resources_required.\
                sdram.per_timestep
            cpu_cycles = placement.vertex.resources_required.cpu_cycles.\
                get_value()
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

        # check if the same structured prov already exists
        if os.path.exists(provenance_filename):
            existing_data = np.load(provenance_filename, allow_pickle=True)
            # TODO check that metadata is correct

            # figure out the past run id
            numerical_runs = [int(
                x) for x in existing_data.files if x not in ["metadata"]]
            prev_run = np.max(numerical_runs)

        else:
            existing_data = {"metadata": metadata}
            prev_run = -1  # no previous run

        # Current data assembly
        current_data = {str(
            prev_run + 1): structured_provenance_df.to_records(
                index=False)}

        # Append current data to existing data
        np.savez_compressed(provenance_filename,
                            **existing_data,
                            **current_data)

    return prov_items


def _add_placement_provenance(placement, txrx, errors):
    """
    :param ~.Placement placement:
    :param ~.Transceiver txrx:
    :param list(str) errors:
    """
    # retrieve provenance data from any cores that provide data
    if isinstance(
            placement.vertex, AbstractProvidesProvenanceDataFromMachine):
        # get data
        try:
            placement.vertex.get_provenance_data_from_machine(
                txrx, placement)
            with ProvenanceWriter() as db:
                db.add_core_name(placement.x, placement.y, placement.p,
                                 placement.vertex.label)
        except Exception:  # pylint: disable=broad-except
            errors.append(traceback.format_exc())
