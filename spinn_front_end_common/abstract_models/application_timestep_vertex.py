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

"""
An Application vertex with a single timestep
"""

import sys
from spinn_utilities.overrides import overrides
from pacman.model.graphs.application import ApplicationVertex
from spinn_front_end_common.utilities import globals_variables


class ApplicationTimestepVertex(ApplicationVertex):

    __slots__ = ["_timestep_in_us"]

    def __init__(self, label=None, constraints=None,
                 max_atoms_per_core=sys.maxsize, timestep_in_us=None):
        """

        :param label: The optional name of the vertex
        :type label: str
        :param constraints: The optional initial constraints of the vertex
        :type constraints: iterable(AbstractConstraint)
        :param max_atoms_per_core: the max number of atoms that can be\
            placed on a core, used in partitioning
        :type max_atoms_per_core: int
        :param timestep_in_us: The timestep in us for ALL macnine vertexes\
            mapped to this vertex
        :type timestep_in_us: int
        :raise PacmanInvalidParameterException:\
            * If one of the constraints is not valid

        """
        super(ApplicationTimestepVertex, self).__init__(
            label=label, max_atoms_per_core=max_atoms_per_core,
            constraints=constraints)
        if timestep_in_us is None:
            self._timestep_in_us = \
                globals_variables.get_simulator().user_time_step_in_us
        else:
            self._timestep_in_us = timestep_in_us

    @property
    def timestep_in_us(self):
        return self._timestep_in_us

    def simtime_in_us_to_timesteps(self, simtime_in_us):
        """
        Helper function to convert simtime in us to whole timestep

        This function verfies that the simtime is a multile of the timestep.

        :param simtime_in_us: a simulation time in us
        :type simtime_in_us: int
        :return: the exact number of timeteps covered by this simtime
        :rtype: int
        :raises ValueError: If the simtime is not a mutlple of the timestep
        """
        n_timesteps = simtime_in_us // self.timestep_in_us
        check = n_timesteps * self.timestep_in_us
        if check != simtime_in_us:
            raise ValueError(
                "The requested time {} is not a multiple of the timestep {}"
                "".format(simtime_in_us, self.timestep_in_us))
        return n_timesteps

    @property
    @overrides(ApplicationVertex.timesteps_in_us)
    def timesteps_in_us(self):
        return set([self.timestep_in_us])
