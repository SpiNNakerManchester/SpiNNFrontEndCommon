# Copyright (c) 2017 The University of Manchester
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

import os
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.profiling import AbstractHasProfileData


_FMT_A = "{: <{}s} {: <7s} {: <14s} {: <14s} {: <14s}\n"
_FMT_B = "{:-<{}s} {:-<7s} {:-<14s} {:-<14s} {:-<14s}\n"
_FMT_C = "{: <{}s} {: >7d} {: >14.6f} {: >14.6f} {: >14.6f}\n"


def profile_data_gatherer():
    """
    Gets all the profiling data recorded by vertices and writes it to files.
    """
    progress = ProgressBar(
        FecDataView.get_n_placements(), "Getting profile data")
    provenance_file_path = FecDataView.get_app_provenance_dir_path()

    # retrieve provenance data from any cores that provide data
    for placement in progress.over(FecDataView.iterate_placemements()):
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
    with open(file_name, "a", encoding="utf-8") as f:
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
