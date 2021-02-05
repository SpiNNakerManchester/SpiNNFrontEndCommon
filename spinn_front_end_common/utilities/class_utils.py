# Copyright (c) 2021 The University of Manchester
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
from spinn_utilities.abstract_base import AbstractBase


def check_class_type(cls, required_type):
    """ Verify that a class is either a subclass of another class or \
        an abstract class.

    This might be used in an abstract class like this::

        def __init_subclass__(cls, **kwargs):  # @NoSelf
            check_class_type(cls, MachineVertex)
            super().__init_subclass__(**kwargs)

    :param type cls: The class to check
    :param type required_type: The class that we want to require
    :raises TypeError: If the type check fails
    """
    if not issubclass(cls, required_type) and type(cls) is not AbstractBase:
        raise TypeError(
            f"{cls.__name__} must be a subclass of {required_type.__name__}")
