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
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.profiling import AbstractHasProfileData


_FMT_A = "{: <{}s} {: <7s} {: <14s} {: <14s} {: <14s}\n"
_FMT_B = "{:-<{}s} {:-<7s} {:-<14s} {:-<14s} {:-<14s}\n"
_FMT_C = "{: <{}s} {: >7d} {: >14.6f} {: >14.6f} {: >14.6f}\n"


def profile_data_gatherer():
    """ Gets all the profiling data recorded by vertices and writes it to\
        files.

    """
    # pylint: disable=too-many-arguments
    placements = FecDataView.get_placements()
    progress = ProgressBar(
        placements.n_placements, "Getting profile data")
    provenance_file_path = FecDataView().app_provenance_dir_path

    # retrieve provenance data from any cores that provide data
    for placement in progress.over(placements):
        if isinstance(placement.vertex, AbstractHasProfileData):
            # get data
            profile_data = placement.vertex.get_profile_data(placement)
            if profile_data.tags:
                _write(placement, profile_data, provenance_file_path)


def _write(p, profile_data, directory):
    """
    :param ~.Placement p:
    :param ProfileData profile_data:
    :param str directory:
    """
    max_tag_len = max(len(tag) for tag in profile_data.tags)
    file_name = os.path.join(
        directory, f"{p.x}_{p.y}_{ p.p}_profile.txt")

    # write profile data to file, creating if necessary
    with open(file_name, "a") as f:
        # Write header
        f.write(_FMT_A.format(
            "tag", max_tag_len, "n_calls", "mean_ms", "n_calls_per_ts",
            "mean_ms_per_ts"))
        f.write(_FMT_B.format("", max_tag_len, "", "", "", ""))

        # Write content
        for tag in profile_data.tags:
            f.write(_FMT_C.format(
                tag, max_tag_len, profile_data.get_n_calls(tag),
                profile_data.get_mean_ms(tag),
                profile_data.get_mean_n_calls_per_ts(tag),
                profile_data.get_mean_ms_per_ts(tag)))
