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


class SpinnFrontEndException(Exception):
    """ Raised when the front end detects an error
    """


class RallocException(SpinnFrontEndException):
    """ Raised when there are not enough routing table entries
    """


class ConfigurationException(SpinnFrontEndException):
    """ Raised when the front end determines a input parameter is invalid
    """


class ExecutableFailedToStartException(SpinnFrontEndException):
    """ Raised when an executable has not entered the expected state during\
        start up
    """


class ExecutableFailedToStopException(SpinnFrontEndException):
    """ Raised when an executable has not entered the expected state during\
        execution
    """


class ExecutableNotFoundException(SpinnFrontEndException):
    """ Raised when a specified executable could not be found
    """


class BufferableRegionTooSmall(SpinnFrontEndException):
    """ Raised when the SDRAM space of the region for buffered packets is\
        too small to contain any packet at all
    """


class BufferedRegionNotPresent(SpinnFrontEndException):
    """ Raised when trying to issue buffered packets for a region not managed
    """
