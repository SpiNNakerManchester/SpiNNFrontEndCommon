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

import sys
from spinn_utilities.overrides import overrides
from pacman.model.constraints.placer_constraints import (
    ChipAndCoreConstraint)
from pacman.model.graphs.application import ApplicationVertex
from pacman.model.resources import ResourceContainer
from pacman.model.graphs import (
    AbstractVirtual, AbstractSpiNNakerLink)
from pacman.model.graphs.machine import MachineSpiNNakerLinkVertex
from spinn_front_end_common.utilities import globals_variables


class ApplicationSpiNNakerLinkVertex(
        ApplicationVertex, AbstractSpiNNakerLink):
    """ A virtual vertex on a SpiNNaker Link.
    """

    __slots__ = [
        "_n_atoms",
        "_spinnaker_link_id",
        "_board_address",
        "_virtual_chip_x",
        "_virtual_chip_y",
        "_timestep"]

    def __init__(
            self, n_atoms, spinnaker_link_id, board_address=None, label=None,
            constraints=None, max_atoms_per_core=sys.maxsize, timestep=None):
        super(ApplicationSpiNNakerLinkVertex, self).__init__(
            label=label, constraints=constraints,
            max_atoms_per_core=max_atoms_per_core)
        self._n_atoms = n_atoms
        self._spinnaker_link_id = spinnaker_link_id
        self._board_address = board_address
        self._virtual_chip_x = None
        self._virtual_chip_y = None
        if timestep is None:
            self._timestep = \
                globals_variables.get_simulator().machine_time_step
        else:
            self._timestep = timestep

    @property
    @overrides(AbstractSpiNNakerLink.spinnaker_link_id)
    def spinnaker_link_id(self):
        return self._spinnaker_link_id

    @property
    @overrides(AbstractVirtual.board_address)
    def board_address(self):
        return self._board_address

    @property
    @overrides(AbstractVirtual.virtual_chip_x)
    def virtual_chip_x(self):
        return self._virtual_chip_x

    @property
    @overrides(AbstractVirtual.virtual_chip_y)
    def virtual_chip_y(self):
        return self._virtual_chip_y

    @overrides(AbstractVirtual.set_virtual_chip_coordinates)
    def set_virtual_chip_coordinates(self, virtual_chip_x, virtual_chip_y):
        self._virtual_chip_x = virtual_chip_x
        self._virtual_chip_y = virtual_chip_y
        self.add_constraint(ChipAndCoreConstraint(
            self._virtual_chip_x, self._virtual_chip_y))

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return self._n_atoms

    @overrides(ApplicationVertex.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):
        return ResourceContainer()

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(
            self, vertex_slice, resources_required, label=None,
            constraints=None):
        vertex = MachineSpiNNakerLinkVertex(
            self._spinnaker_link_id, self._board_address, label, constraints)
        return vertex

    @property
    @overrides(ApplicationVertex.timestep)
    def timestep(self):
        return self._timestep
