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

from pacman.model.graphs.application.abstract import (
    AbstractOneAppOneMachineVertex)
from .extra_monitor_support_machine_vertex import (
    ExtraMonitorSupportMachineVertex)


class ExtraMonitorSupport(AbstractOneAppOneMachineVertex):
    """ Control over the extra monitors.
    """
    __slots__ = []

    def __init__(self, x, y, *, constraints=()):
        """
        :param int x: The X coordinate of the vertex
        :param int y: The Y coordinate of the vertex
        :param constraints: The additional constraints on the vertex
        :type constraints:
            iterable(~pacman.model.constraints.AbstractConstraint)
        """
        super().__init__(
            ExtraMonitorSupportMachineVertex(
                x, y, self, constraints=constraints),
            label="ExtraMonitorSupport", constraints=constraints)
