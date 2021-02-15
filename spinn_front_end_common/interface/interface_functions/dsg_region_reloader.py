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
from spinn_machine import SDRAM
from data_specification import DataSpecificationExecutor
from data_specification.constants import MAX_MEM_REGIONS
from data_specification.utility_calls import (
    get_region_base_address_offset, get_data_spec_and_file_writer_filename)
from spinn_front_end_common.abstract_models import (
    AbstractRewritesDataSpecification)
from spinn_front_end_common.utilities.helpful_functions import (
    generate_unique_folder_name, n_word_struct)


class DSGRegionReloader(object):
    """ Regenerates and reloads the data specifications.
    """
    __slots__ = [
        "_txrx", "_host", "_write_text", "_rpt_dir", "_data_dir"]

    def __call__(
            self, transceiver, placements, hostname, report_directory,
            write_text_specs):
        """
        :param ~spinnman.transceiver.Transceiver transceiver:
            SpiNNMan transceiver for communication
        :param ~pacman.model.placements.Placements placements:
            the list of placements of the machine graph to cores
        :param str hostname:
            the machine name
        :param str report_directory:
            the location where reports are stored
        :param bool write_text_specs:
            Whether the textual version of the specification is to be written
        """
        # pylint: disable=too-many-arguments, attribute-defined-outside-init
        self._txrx = transceiver
        self._host = hostname
        self._write_text = write_text_specs

        # build file paths for reloaded stuff
        app_data_dir = generate_unique_folder_name(
            report_directory, "reloaded_data_regions", "")
        if not os.path.exists(app_data_dir):
            os.makedirs(app_data_dir)
        self._data_dir = app_data_dir

        report_dir = None
        if write_text_specs:
            report_dir = generate_unique_folder_name(
                report_directory, "reloaded_data_regions", "")
            if not os.path.exists(report_dir):
                os.makedirs(report_dir)
        self._rpt_dir = report_dir

        progress = ProgressBar(placements.n_placements, "Reloading data")
        for placement in progress.over(placements.placements):
            # Generate the data spec for the placement if needed
            self._regenerate_data_spec_for_vertices(placement)

        # App data directory can be removed as should be empty
        os.rmdir(app_data_dir)

    def _regenerate_data_spec_for_vertices(self, placement):
        """
        :param ~.Placement placement:
        """
        vertex = placement.vertex

        # If the vertex doesn't regenerate, skip
        if not isinstance(vertex, AbstractRewritesDataSpecification):
            return

        # If the vertex doesn't require regeneration, skip
        if not vertex.reload_required():
            return

        # build the writers for the reports and data
        spec_file, spec = get_data_spec_and_file_writer_filename(
            placement.x, placement.y, placement.p, self._host,
            self._rpt_dir, self._write_text, self._data_dir)

        # Execute the regeneration
        vertex.regenerate_data_specification(spec, placement)

        # execute the spec
        with open(spec_file, "rb") as spec_reader:
            data_spec_executor = DataSpecificationExecutor(
                spec_reader, SDRAM.max_sdram_found)
            data_spec_executor.execute()
        try:
            os.remove(spec_file)
        except Exception:  # pylint: disable=broad-except
            # Ignore the deletion of files as non-critical
            pass

        # Read the region table for the placement
        regions_base_address = self._txrx.get_cpu_information_from_core(
            placement.x, placement.y, placement.p).user[0]
        start_region = get_region_base_address_offset(regions_base_address, 0)
        table_size = get_region_base_address_offset(
            regions_base_address, MAX_MEM_REGIONS) - start_region
        offsets = n_word_struct(MAX_MEM_REGIONS).unpack_from(
            self._txrx.read_memory(
                placement.x, placement.y, start_region, table_size))

        # Write the regions to the machine
        for i, region in enumerate(data_spec_executor.dsef.mem_regions):
            if region is not None and not region.unfilled:
                self._txrx.write_memory(
                    placement.x, placement.y, offsets[i],
                    region.region_data[:region.max_write_pointer])
        vertex.set_reload_required(False)
