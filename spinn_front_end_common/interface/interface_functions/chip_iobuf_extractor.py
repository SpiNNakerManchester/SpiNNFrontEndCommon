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

from spinn_front_end_common.utilities import IOBufExtractor


class ChipIOBufExtractor(object):
    """ Extract the logging output buffers from the machine, and separates\
        lines based on their prefix.
    """

    __slots__ = []

    def __call__(
            self, transceiver, executable_targets, executable_finder,
            app_provenance_file_path=None, system_provenance_file_path=None,
            from_cores="ALL", binary_types=None):
        """
        :param ~spinnman.transceiver.Transceiver transceiver:
        :param ~spinnman.model.ExecutableTargets executable_targets:
        :param ExecutableFinder executable_finder:
        :param app_provenance_file_path:
        :type app_provenance_file_path: str or None
        :param system_provenance_file_path:
        :type system_provenance_file_path: str or None
        :param str from_cores:
        :param str binary_types:
        :return: error_entries, warn_entries
        :rtype: tuple(list(str),list(str))
        """
        extractor = IOBufExtractor(
            transceiver, executable_targets, executable_finder,
            app_provenance_file_path, system_provenance_file_path, from_cores,
            binary_types)
        return extractor.extract_iobuf()
