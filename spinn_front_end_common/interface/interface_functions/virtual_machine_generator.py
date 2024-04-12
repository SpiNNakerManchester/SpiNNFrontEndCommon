# Copyright (c) 2015 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
from spinn_utilities.config_holder import (
    get_config_int, get_config_int_or_none, get_config_str_or_none,
    is_config_none)
from spinn_utilities.log import FormatAdapter
from spinn_machine import json_machine, Machine
from spinn_machine.virtual_machine import (
    virtual_machine, virtual_machine_by_boards, virtual_machine_by_chips)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.utilities.exceptions import ConfigurationException
logger = FormatAdapter(logging.getLogger(__name__))


def virtual_machine_generator() -> Machine:
    """
    Generates a virtual machine with given dimensions and configuration.

    :return: The virtual machine.
    :rtype: ~spinn_machine.Machine
    :raises Exception: If given bad arguments
    """

    json_path = get_config_str_or_none("Machine", "json_path")
    if json_path is None:
        if is_config_none("Machine", "width") or \
                is_config_none("Machine", "height"):
            if FecDataView.has_n_boards_required():
                n_boards = FecDataView.get_n_boards_required()
                machine = virtual_machine_by_boards((n_boards))
            elif FecDataView.has_n_chips_needed():
                n_chips = FecDataView.get_n_chips_needed()
                machine = virtual_machine_by_chips((n_chips))
            else:
                height = get_config_int_or_none("Machine", "height")
                width = get_config_int_or_none("Machine", "width")
                raise ConfigurationException(
                    "Unable to create a VirtualMachine at this time unless "
                    "both width and heigth are specified in the cfg found "
                    f"found {width=} {height=}")
        else:
            height = get_config_int("Machine", "height")
            width = get_config_int("Machine", "width")
            machine = virtual_machine(
                width=width, height=height, validate=True)
    else:
        if (not is_config_none("Machine", "width") or
                not is_config_none("Machine", "height") or
                not is_config_none("Machine", "down_chips") or
                not is_config_none("Machine", "down_cores") or
                not is_config_none("Machine", "down_links")):
            logger.warning("As json_path specified all other virtual "
                           "machine settings ignored.")
        machine = json_machine.machine_from_json(json_path)

    # Work out and add the SpiNNaker links and FPGA links
    machine.add_spinnaker_links()
    machine.add_fpga_links()

    logger.info("Created {}", machine.summary_string())

    return machine
