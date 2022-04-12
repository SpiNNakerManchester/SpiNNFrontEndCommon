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
from typing import Dict, Iterable, List, Tuple, Union
from spalloc import ProtocolClient
from spinn_utilities.config_holder import get_config_int, get_config_str
from spinn_machine import Machine, virtual_machine
from spinnman.spalloc import is_server_address, SpallocClient
from spinn_front_end_common.utilities.spalloc import parse_old_spalloc


def spalloc_max_machine_generator(bearer_token: str = None) -> Machine:
    """
    Generates a maximum virtual machine a given allocation server can generate.

    :param str bearer_token: The bearer token to use
    :return: A virtual machine
    :rtype: ~spinn_machine.Machine
    """
    spalloc_server = get_config_str("Machine", "spalloc_server")
    spalloc_machine = get_config_str("Machine", "spalloc_machine")
    if is_server_address(spalloc_server):
        width, height = discover_max_machine_area_new(
            spalloc_server, spalloc_machine, bearer_token)
    else:
        spalloc_port = get_config_int("Machine", "spalloc_port")
        width, height = discover_max_machine_area_old(
            spalloc_server, spalloc_port, spalloc_machine)

    if width is None:
        raise Exception(
            "The spalloc server appears to have no compatible machines")

    max_machine_core_reduction = get_config_int(
        "Machine", "max_machine_core_reduction")
    n_cpus_per_chip = (Machine.max_cores_per_chip() -
                       max_machine_core_reduction)

    # Return the width and height, and make no assumption about wrap-
    # arounds or version.
    return virtual_machine(
        width=width, height=height,
        n_cpus_per_chip=n_cpus_per_chip, validate=False)


def discover_max_machine_area_new(
        spalloc_server: str, spalloc_machine: Union[str, None],
        bearer_token: str = None) -> Union[Tuple[int, int], Tuple[None, None]]:
    """
    Generate a maximum virtual machine a given allocation server can
    generate, communicating with the spalloc server using the new protocol.

    :param str spalloc_server: Spalloc server URL
    :param spalloc_machine: Desired machine name, or ``None`` for default.
    :type spalloc_machine: str or None
    :param bearer_token: The bearer token to use
    :type bearer_token: str or None
    :return: the dimensions of the maximum machine, in chips
    :rtype: tuple(int or None,int or None)
    """
    max_dimensions = (None, None)
    max_area = -1
    num_dead = 0

    with SpallocClient(spalloc_server, bearer_token=bearer_token) as c:
        for machine in c.list_machines().values():
            if spalloc_machine is not None:
                if spalloc_machine != machine.name:
                    continue
            else:
                if "default" not in machine.tags:
                    continue

            # The "biggest" board is the one with the most chips
            if machine.width * machine.height > max_area:
                max_area = machine.width * machine.height
                max_dimensions = (machine.width * 12, machine.height * 12)
                num_dead = len(machine.dead_boards)

    # Handle special case of a single board
    if max_area == 1 and num_dead == 2:
        return 8, 8
    return max_dimensions


def discover_max_machine_area_old(
        spalloc_server: str, spalloc_port: int,
        spalloc_machine: Union[str, None]) -> Union[
            Tuple[int, int], Tuple[None, None]]:
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
    host, port, _user = parse_old_spalloc(spalloc_server, spalloc_port)
    with ProtocolClient(host, port) as client:
        machines = client.list_machines()
        # Close the context immediately; don't want to keep this particular
        # connection around as there's not a great chance of this code
        # being rerun in this process any time soon.

    max_size = (None, None)
    max_area = -1
    for machine in _filter(machines, spalloc_machine):
        # Get the width and height in chips, and logical area in chips**2
        width, height, area = _get_size(machine)

        # The "biggest" board is the one with the most chips
        if area > max_area:
            max_area = area
            max_size = (width, height)
    return max_size


def _filter(machines: List[Dict[str, str]],
            target_name: Union[str, None]) -> Iterable[Dict[str, str]]:
    """
    :param list(dict(str,str)) machines:
    :param str target_name:
    :rtype: iterable(dict(str,str or int))
    """
    if target_name is None:
        return (m for m in machines if "default" in m["tags"])
    return (m for m in machines if m["name"] == target_name)


def _get_size(machine: Dict[str, int]) -> Tuple[int, int, int]:
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
