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

import os
from spinn_utilities.config_holder import (
    add_default_cfg, clear_cfg_files)
from spinnman.config_setup import add_spinnman_cfg
from pacman.config_setup import add_pacman_cfg
from data_specification.config_setup import add_data_specification_cfg
from spinn_front_end_common.utilities.globals_variables import (
    setup_for_unittest)

BASE_CONFIG_FILE = "spinnaker.cfg"


def unittest_setup():
    """
    Does all the steps that may be required before a unittest

    Resets the configs so only the local default configs are included.

    Unsets any previous simulators and tempdirs

    .. note::
        This file should only be called from spinn_front_end_common tests

    """
    setup_for_unittest()
    clear_cfg_files(True)
    add_spinnaker_cfg()


def add_spinnaker_cfg():
    """
    Add the local cfg and all dependent cfg files.
    """
    add_pacman_cfg()  # This add its dependencies too
    add_spinnman_cfg()  # double adds of dependencies ignored
    add_data_specification_cfg()  # double adds of dependencies ignored
    add_default_cfg(os.path.join(os.path.dirname(__file__), BASE_CONFIG_FILE))
