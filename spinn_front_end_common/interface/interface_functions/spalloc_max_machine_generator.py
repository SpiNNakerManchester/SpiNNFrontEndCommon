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

from spalloc import ProtocolClient
from spinn_machine.virtual_machine import virtual_machine
from spinn_machine.machine import Machine
from spinn_front_end_common.utilities.spalloc import SpallocClient


class SpallocMaxMachineGenerator(object):
    """ Generates a maximum virtual machine a given allocation server can\
        generate.
    """

    __slots__ = []

    def __call__(
            self, spalloc_server, spalloc_port=22244, spalloc_machine=None,
            max_machine_core_reduction=0):
        """
        :param str spalloc_server:
        :param int spalloc_port:
        :param str spalloc_machine:
        :param int max_machine_core_reduction: the number of cores less than
            :py:const:`~spinn_machine.Machine.DEFAULT_MAX_CORES_PER_CHIP`
            that each chip should have
        :return: A virtual machine
        :rtype: ~spinn_machine.Machine
        """
        if SpallocClient.is_server_address(spalloc_server):
            width, height = self.discover_max_machine_area_new(
                spalloc_server, spalloc_machine)
        else:
            width, height = self.discover_max_machine_area_old(
                spalloc_server, spalloc_port, spalloc_machine)

        if width is None:
            raise Exception(
                "The spalloc server appears to have no compatible machines")

        n_cpus_per_chip = (Machine.max_cores_per_chip() -
                           max_machine_core_reduction)

        # Return the width and height, and make no assumption about wrap-
        # arounds or version.
        return virtual_machine(
            width=width, height=height,
            n_cpus_per_chip=n_cpus_per_chip, validate=False)

    def discover_max_machine_area_new(self, spalloc_server, spalloc_machine):
        """
        Generate a maximum virtual machine a given allocation server can
        generate, communicating with the spalloc server using the new protocol.

        :param str spalloc_server: Spalloc server URL
        :param spalloc_machine: Desired machine name, or ``None`` for default.
        :type spalloc_machine: str or None
        :return: the dimensions of the maximum machine
        :rtype: tuple(int or None,int or None)
        """
        max_width = None
        max_height = None
        max_area = -1

        with SpallocClient(spalloc_server) as client:
            for machine in client.list_machines().values():
                if spalloc_machine is not None:
                    if spalloc_machine != machine.name:
                        continue
                else:
                    if "default" not in machine.tags:
                        continue

                # The "biggest" board is the one with the most chips
                if machine.area > max_area:
                    max_area = machine.area
                    max_width = machine.width
                    max_height = machine.height

        return max_width, max_height

    def discover_max_machine_area_old(
            self, spalloc_server, spalloc_port, spalloc_machine):
        """
        Generate a maximum virtual machine a given allocation server can
        generate, communicating with the spalloc server using the old protocol.

        :param str spalloc_server: Spalloc server hostname
        :param int spalloc_port: Spalloc server port
        :param spalloc_machine: Desired machine name, or ``None`` for default.
        :type spalloc_machine: str or None
        :return: the dimensions of the maximum machine
        :rtype: tuple(int or None,int or None)
        """
        with ProtocolClient(spalloc_server, spalloc_port) as client:
            machines = client.list_machines()
            # Close the context immediately; don't want to keep this particular
            # connection around as there's not a great chance of this code
            # being rerun in this process any time soon.
        max_width = None
        max_height = None
        max_area = -1

        for machine in self._filter_old(machines, spalloc_machine):
            # Get the width and height in chips, and logical area in chips**2
            width, height, area = self._get_size(machine)

            # The "biggest" board is the one with the most chips
            if area > max_area:
                max_area = area
                max_width = width
                max_height = height

        return max_width, max_height

    @staticmethod
    def _filter_old(machines, target_name):
        """
        :param list(dict(str,str)) machines:
        :param str target_name:
        :rtype: iterable(dict(str,str or int))
        """
        if target_name is None:
            return (m for m in machines if "default" in m["tags"])
        return (m for m in machines if m["name"] == target_name)

    @staticmethod
    def _get_size(machine):
        """
        :param dict(str,int) machine:
        :return: width, height, area
        :rtype: tuple(int,int,int)
        """
        # Get the width and height in chips
        width = machine["width"] * 12
        height = machine["height"] * 12

        # A specific exception is the 1-board machine, which is represented as
        # a 3 board machine with 2 dead boards. In this case the width and
        # height are 8.
        if (machine["width"] == 1 and
                machine["height"] == 1 and
                len(machine["dead_boards"]) == 2):
            return 8, 8, 48

        return width, height, width * height
