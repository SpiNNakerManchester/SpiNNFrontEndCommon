# Copyright (c) 2020 The University of Manchester
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


class BadArgs(Exception):
    """ Bad number of arguments to a command.
    """
    def __str__(self):
        return "bad args"


class StructParseException(Exception):
    """ Parsing exception handling structure definition. """


class SpinnException(Exception):
    """ General exception from the comms layer or SpiNNaker. """


class SpinnTooManyRetriesException(SpinnException):
    """ Too many retries were required. """
