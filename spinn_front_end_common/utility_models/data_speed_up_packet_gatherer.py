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

from spinn_utilities.overrides import overrides
from pacman.model.graphs.application import ApplicationVertex
from spinn_front_end_common.abstract_models import (
    AbstractHasAssociatedBinary, AbstractGeneratesDataSpecification)
from .data_speed_up_packet_gatherer_machine_vertex import (
    DataSpeedUpPacketGatherMachineVertex)


class DataSpeedUpPacketGather(
        ApplicationVertex, AbstractGeneratesDataSpecification,
        AbstractHasAssociatedBinary):
    """ The gatherer for the data speed up protocols. Gatherers are only ever\
        deployed on chips with an ethernet connection.
    """
    __slots__ = ["_machine_vertex"]

    def __init__(
            self, x, y, ip_address, extra_monitors_by_chip,
            report_default_directory,
            write_data_speed_up_reports, constraints=None):
        """
        :param x: Where this gatherer is.
        :type x: int
        :param y: Where this gatherer is.
        :type y: int
        :param extra_monitors_by_chip: UNUSED
        :type extra_monitors_by_chip: \
            dict(tuple(int,int), ExtraMonitorSupportMachineVertex)
        :param ip_address: \
            How to talk directly to the chip where the gatherer is.
        :type ip_address: str
        :param report_default_directory: Where reporting is done.
        :type report_default_directory: str
        :param write_data_speed_up_reports: \
            Whether to write low-level reports on data transfer speeds.
        :type write_data_speed_up_reports: bool
        :param constraints:
        :type constraints: \
            iterable(~pacman.model.constraints.AbstractConstraint)
        """
        super(DataSpeedUpPacketGather, self).__init__(
            "multicast speed up application vertex for {}, {}".format(
                x, y), constraints, 1)
        self._machine_vertex = DataSpeedUpPacketGatherMachineVertex(
            x=x, y=y, ip_address=ip_address, constraints=constraints,
            extra_monitors_by_chip=extra_monitors_by_chip,
            report_default_directory=report_default_directory,
            write_data_speed_up_reports=write_data_speed_up_reports)

    @property
    def machine_vertex(self):
        return self._machine_vertex

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return self._machine_vertex.get_binary_file_name()

    @overrides(ApplicationVertex.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):
        return self._machine_vertex.resources_required

    @overrides(ApplicationVertex.create_machine_vertex)
    def create_machine_vertex(self, vertex_slice, resources_required,
                              label=None, constraints=None):
        return self._machine_vertex

    @overrides(AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(self, spec, placement):
        placement.vertex.generate_data_specification(spec, placement)

    @property
    @overrides(ApplicationVertex.n_atoms)
    def n_atoms(self):
        return 1

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return self._machine_vertex.get_binary_start_type()
