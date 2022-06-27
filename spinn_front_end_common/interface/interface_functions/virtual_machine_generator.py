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

import logging
from spinn_utilities.config_holder import get_config_int, get_config_str
from spinn_utilities.log import FormatAdapter
from spinn_machine import json_machine, virtual_machine, Machine
logger = FormatAdapter(logging.getLogger(__name__))


def virtual_machine_generator():
    """ Generates a virtual machine with given dimensions and configuration.

    :return: The virtual machine.
    :rtype: ~spinn_machine.Machine
    :raises Exception: If given bad arguments
    """
    height = get_config_int("Machine", "height")
    width = get_config_int("Machine", "width")
    json_path = get_config_str("Machine", "json_path")

    # For backward compatibility support version in csf files for now
    version = get_config_int("Machine", "version")
    if version is not None:
        if version in [2, 3]:
            if height is None:
                height = 2
            else:
                assert height == 2
            if width is None:
                width = 2
            else:
                assert width == 2
            logger.warning("For virtual Machines version is deprecated."
                           "use width=2, height=2 instead")
        elif version in [4, 5]:
            if height is None:
                height = 8
            else:
                assert height == 8
            if width is None:
                width = 8
            else:
                assert width == 8
            logger.warning("For virtual Machines version is deprecated."
                           "use width=8, height=8 instead")
        else:
            raise Exception("Unknown version {}".format(version))

    if json_path is None:
        machine = virtual_machine(
            width=width, height=height,
            n_cpus_per_chip=Machine.max_cores_per_chip(),
            validate=True)
    else:
        if (height is not None or width is not None or
                version is not None or
                get_config_str("Machine", "down_chips") is not None or
                get_config_str("Machine", "down_cores") is not None or
                get_config_str("Machine", "down_links") is not None):
            logger.warning("As json_path specified all other virtual "
                           "machine settings ignored.")
        machine = json_machine.machine_from_json(json_path)

    # Work out and add the SpiNNaker links and FPGA links
    machine.add_spinnaker_links()
    machine.add_fpga_links()

    logger.info(
        "Created a virtual machine which has {}".format(
            machine.cores_and_link_output_string()))

    return machine
