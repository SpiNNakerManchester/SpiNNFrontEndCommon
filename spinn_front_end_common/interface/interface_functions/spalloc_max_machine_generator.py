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
from spinn_utilities.config_holder import get_config_int, get_config_str
from spinn_machine.virtual_machine import virtual_machine
from spinn_machine.machine import Machine


def spalloc_max_machine_generator(spalloc_server):
    """
    Generates a maximum virtual machine a given allocation server can generate.

    :param str spalloc_server:
    :return: A virtual machine
    :rtype: ~spinn_machine.Machine
    """
    spalloc_port = get_config_int("Machine", "spalloc_port")
    spalloc_machine = get_config_str("Machine", "spalloc_machine")
    max_machine_core_reduction = get_config_int(
        "Machine", "max_machine_core_reduction")

    with ProtocolClient(spalloc_server, spalloc_port) as client:
        machines = client.list_machines()
        # Close the context immediately; don't want to keep this particular
        # connection around as there's not a great chance of this code
        # being rerun in this process any time soon.
    max_width = None
    max_height = None
    max_area = -1

    for machine in _filter(machines, spalloc_machine):
        # Get the width and height in chips, and logical area in chips**2
        width, height, area = _get_size(machine)

        # The "biggest" board is the one with the most chips
        if area > max_area:
            max_area = area
            max_width = width
            max_height = height

    if max_width is None:
        raise Exception(
            "The spalloc server appears to have no compatible machines")

    n_cpus_per_chip = (Machine.max_cores_per_chip() -
                       max_machine_core_reduction)

    # Return the width and height, and make no assumption about wrap-
    # arounds or version.
    return virtual_machine(
        width=max_width, height=max_height,
        n_cpus_per_chip=n_cpus_per_chip, validate=False)


def _filter(machines, target_name):
    """
    :param list(dict(str,str)) machines:
    :param str target_name:
    :rtype: iterable(dict(str,str or int))
    """
    if target_name is None:
        return (m for m in machines if "default" in m["tags"])
    return (m for m in machines if m["name"] == target_name)


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
