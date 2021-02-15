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
from .data_speed_up_packet_gatherer_machine_vertex import (
    DataSpeedUpPacketGatherMachineVertex)


class DataSpeedUpPacketGather(AbstractOneAppOneMachineVertex):
    """ The gatherer for the data speed up protocols. Gatherers are only ever\
        deployed on chips with an ethernet connection.
    """
    __slots__ = []

    def __init__(
            self, x, y, ip_address, extra_monitors_by_chip,
            report_default_directory,
            write_data_speed_up_reports, constraints=None):
        """
        :param int x: Where this gatherer is.
        :param int y: Where this gatherer is.
        :param extra_monitors_by_chip: UNUSED
        :type extra_monitors_by_chip:
            dict(tuple(int,int), ExtraMonitorSupportMachineVertex)
        :param str ip_address:
            How to talk directly to the chip where the gatherer is.
        :param str report_default_directory: Where reporting is done.
        :param bool write_data_speed_up_reports:
            Whether to write low-level reports on data transfer speeds.
        :param constraints:
        :type constraints:
            iterable(~pacman.model.constraints.AbstractConstraint)
        """
        super().__init__(
            DataSpeedUpPacketGatherMachineVertex(
                app_vertex=self,
                x=x, y=y, ip_address=ip_address, constraints=constraints,
                extra_monitors_by_chip=extra_monitors_by_chip,
                report_default_directory=report_default_directory,
                write_data_speed_up_reports=write_data_speed_up_reports),
            "multicast speed up application vertex for {}, {}".format(
                x, y), constraints)
