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

from spinn_front_end_common.utilities.iobuf_extractor import IOBufExtractor


def chip_io_buf_extractor(executable_targets):
    """ Extract the logging output buffers from the machine, and separates\
        lines based on their prefix.

    :param ~spinnman.model.ExecutableTargets executable_targets:
    :return: error_entries, warn_entries
    :rtype: tuple(list(str),list(str))
    """
    extractor = IOBufExtractor(executable_targets)
    return extractor.extract_iobuf()
