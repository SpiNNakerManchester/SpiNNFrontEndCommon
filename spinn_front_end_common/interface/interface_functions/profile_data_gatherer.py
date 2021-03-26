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
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.utilities.constants import (
    MICRO_TO_MILLISECOND_CONVERSION)
from spinn_front_end_common.interface.profiling import AbstractHasProfileData


class ProfileDataGatherer(object):
    """ Gets all the profiling data recorded by vertices and writes it to\
        files.
    """

    __slots__ = []

    def __call__(
            self, transceiver, placements, provenance_file_path,
            machine_time_step):
        """
        :param ~spinnman.transceiver.Transceiver transceiver:
            the SpiNNMan interface object
        :param ~pacman.model.placements.Placements placements:
            The placements of the vertices
        :param str provenance_file_path:
            The location to store the profile data
        :param int machine_time_step:
            machine time step in ms
        """
        # pylint: disable=too-many-arguments
        machine_time_step_ms = (
            float(machine_time_step) / MICRO_TO_MILLISECOND_CONVERSION)

        progress = ProgressBar(
            placements.n_placements, "Getting profile data")

        # retrieve provenance data from any cores that provide data
        for placement in progress.over(placements.placements):
            if isinstance(placement.vertex, AbstractHasProfileData):
                # get data
                profile_data = placement.vertex.get_profile_data(
                    transceiver, placement)
                if profile_data.tags:
                    self._write(placement, profile_data, machine_time_step_ms,
                                provenance_file_path)

    _FMT_A = "{: <{}s} {: <7s} {: <14s} {: <14s} {: <14s}\n"
    _FMT_B = "{:-<{}s} {:-<7s} {:-<14s} {:-<14s} {:-<14s}\n"
    _FMT_C = "{: <{}s} {: >7d} {: >14.6f} {: >14.6f} {: >14.6f}\n"

    @classmethod
    def _write(cls, p, profile_data, machine_time_step_ms, directory):
        """
        :param ~.Placement p:
        :param ProfileData profile_data:
        :param float machine_time_step_ms:
        :param str directory:
        """
        max_tag_len = max(len(tag) for tag in profile_data.tags)
        file_name = os.path.join(
            directory, "{}_{}_{}_profile.txt".format(p.x, p.y, p.p))

        # write profile data to file, creating if necessary
        with open(file_name, "a") as f:
            # Write header
            f.write(cls._FMT_A.format(
                "tag", max_tag_len, "n_calls", "mean_ms", "n_calls_per_ts",
                "mean_ms_per_ts"))
            f.write(cls._FMT_B.format("", max_tag_len, "", "", "", ""))

            # Write content
            for tag in profile_data.tags:
                f.write(cls._FMT_C.format(
                    tag, max_tag_len, profile_data.get_n_calls(tag),
                    profile_data.get_mean_ms(tag),
                    profile_data.get_mean_n_calls_per_ts(
                        tag, machine_time_step_ms),
                    profile_data.get_mean_ms_per_ts(
                        tag, machine_time_step_ms)))
