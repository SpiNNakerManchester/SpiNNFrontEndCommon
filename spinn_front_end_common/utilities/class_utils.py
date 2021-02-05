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


def require_subclass(required_class):
    """ Decorator that arranges for subclasses of the decorated class to\
        require that they are also subclasses of the given class.

    :param type required_class:
        The class that the subclass of the decorated class must be an instance
        of (if that subclass is concrete).
    """

    # Beware! This is all deep shenanigans!
    #
    # The __init_subclass__ stuff is from
    #     https://stackoverflow.com/a/45400374/301832
    # The setattr() call is from:
    #     https://stackoverflow.com/a/533583/301832
    # The classmethod() call is from:
    #     https://stackoverflow.com/a/17930262/301832
    # The use of __class__ to enable super() to work is from:
    #     https://stackoverflow.com/a/43779009/301832
    # The need to do this as a functional decorator is my own discovery;
    # without it, some very weird interactions with metaclasses happen and I
    # really don't want to debug that stuff.

    def decorate(target_class):
        # pylint: disable=unused-variable
        __class__ = target_class  # @ReservedAssignment # noqa: F841

        def __init_subclass__(cls, **kwargs):
            if not issubclass(cls, required_class) and \
                    type(cls) is not AbstractBase:
                raise TypeError(
                    f"{cls.__name__} must be a subclass "
                    f"of {required_class.__name__}")
            super().__init_subclass__(**kwargs)

        setattr(target_class, '__init_subclass__',
                classmethod(__init_subclass__))
        return target_class
    return decorate
