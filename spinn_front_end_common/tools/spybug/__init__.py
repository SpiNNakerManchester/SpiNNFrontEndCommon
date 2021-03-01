# Copyright (c) 2013-2020 The University of Manchester
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

"""
The implementation of the ``spybug`` program, which is a conversion of the
original ``ypbug`` program (from ``spinnaker_tools``) to Python.

The implementation is in :py:func:`~.spybug.main`.
"""

from .cli import CLI
from .scp import SCP
from .cmd import Cmd, SCAMPCmd, BMPCmd
from .sv import Struct
from .exn import (
    SpinnException, SpinnTooManyRetriesException, StructParseException)

__all__ = ("CLI", "SCP", "Cmd", "SCAMPCmd", "BMPCmd", "Struct",
           "SpinnException", "SpinnTooManyRetriesException",
           "StructParseException")
