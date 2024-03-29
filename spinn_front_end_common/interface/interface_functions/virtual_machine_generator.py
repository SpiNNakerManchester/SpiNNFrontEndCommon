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
    get_config_int, get_config_str_or_none, is_config_none)
from spinn_utilities.log import FormatAdapter
from spinn_machine import json_machine, virtual_machine, Machine
logger = FormatAdapter(logging.getLogger(__name__))


def virtual_machine_generator() -> Machine:
    """
    Generates a virtual machine with given dimensions and configuration.

    :return: The virtual machine.
    :rtype: ~spinn_machine.Machine
    :raises Exception: If given bad arguments
    """
    height = get_config_int("Machine", "height")
    width = get_config_int("Machine", "width")

    json_path = get_config_str_or_none("Machine", "json_path")
    if json_path is None:
        assert width is not None and height is not None
        machine = virtual_machine(width=width, height=height, validate=True)
    else:
        if (height is not None or width is not None or
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
