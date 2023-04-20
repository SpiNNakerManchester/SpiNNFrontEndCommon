# Copyright (c) 2014 The University of Manchester
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


class SpinnFrontEndException(Exception):
    """
    Raised when the front end detects an error.
    """


class RallocException(SpinnFrontEndException):
    """
    Raised when there are not enough routing table entries.
    """


class ConfigurationException(SpinnFrontEndException):
    """
    Raised when the front end determines a input parameter is invalid.
    """


class ExecutableFailedToStartException(SpinnFrontEndException):
    """
    Raised when an executable has not entered the expected state during
    start up.
    """


class ExecutableFailedToStopException(SpinnFrontEndException):
    """
    Raised when an executable has not entered the expected state during
    execution.
    """


class ExecutableNotFoundException(SpinnFrontEndException):
    """
    Raised when a specified executable could not be found.
    """


class BufferableRegionTooSmall(SpinnFrontEndException):
    """
    Raised when the SDRAM space of the region for buffered packets is
    too small to contain any packet at all.
    """


class BufferedRegionNotPresent(SpinnFrontEndException):
    """
    Raised when trying to issue buffered packets for a region not managed.
    """


class CantFindSDRAMToUseException(SpinnFrontEndException):
    """
    Raised when malloc and SDRAM stealing cannot occur.
    """


class DsDatabaseException(SpinnFrontEndException):
    """
    Raise when a query in the Data Specification database failed.
    """
