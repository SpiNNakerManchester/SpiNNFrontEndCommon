# Copyright (c) 2022-202 The University of Manchester
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

from pacman.model.graphs.application import ApplicationEdge


class WrapperApplicationEdge(ApplicationEdge):

    def __init__(self, machine_edge):
        pre_vertex = machine_edge.pre_vertex.app_vertex
        post_vertex = machine_edge.post_vertex.app_vertex
        super().__init__(pre_vertex, post_vertex, machine_edge.label)
        machine_edge._app_edge = self
