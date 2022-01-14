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

import logging
from spinn_utilities.log import FormatAdapter
from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.buffer_management.buffer_models \
    import (
        AbstractReceiveBuffersToHost)

logger = FormatAdapter(logging.getLogger(__name__))


def buffer_extractor():
    """ Extracts data in between runs.

    """
    # Count the regions to be read
    n_regions_to_read, recording_placements = _count_regions()
    if not n_regions_to_read:
        logger.info("No recorded data to extract")
        return

    # Read back the regions
    progress = ProgressBar(
        n_regions_to_read, "Extracting buffers from the last run")
    buffer_manager = FecDataView.get_buffer_manager()
    try:
        buffer_manager.get_data_for_placements(
            recording_placements, progress)
    finally:
        progress.end()


def _count_regions():
    """
    :rtype: tuple(int, list(~.Placement))
    """
    # Count the regions to be read
    n_regions_to_read = 0
    recording_placements = list()
    for vertex in FecDataView.get_runtime_machine_graph().vertices:
        if isinstance(vertex, AbstractReceiveBuffersToHost):
            n_regions_to_read += len(vertex.get_recorded_region_ids())
            placement = FecDataView.get_placement_of_vertex(vertex)
            recording_placements.append(placement)
    return n_regions_to_read, recording_placements
