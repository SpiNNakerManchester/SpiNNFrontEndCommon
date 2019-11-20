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
import struct
from spinn_utilities.progress_bar import ProgressBar
from spinn_machine import SDRAM
from spinn_storage_handlers import FileDataReader
from data_specification import DataSpecificationExecutor
from data_specification.constants import MAX_MEM_REGIONS
from data_specification.utility_calls import (
    get_region_base_address_offset, get_data_spec_and_file_writer_filename)
from spinn_front_end_common.abstract_models import (
    AbstractRewritesDataSpecification)
from spinn_front_end_common.utilities.helpful_functions import (
    generate_unique_folder_name)

REGION_STRUCT = struct.Struct("<{}I".format(MAX_MEM_REGIONS))


class DSGRegionReloader(object):
    """ Regenerates and reloads the data specifications.
    """
    __slots__ = []

    def __call__(
            self, transceiver, placements, hostname, report_directory,
            write_text_specs, application_data_file_path, graph_mapper=None):
        """
        :param transceiver: SpiNNMan transceiver for communication
        :param placements: the list of placements of the machine graph to cores
        :param hostname: the machine name
        :param report_directory: the location where reports are stored
        :param write_text_specs:\
            True if the textual version of the specification is to be written
        :param application_data_file_path:\
            Folder where data specifications should be written to
        :param graph_mapper:\
            the mapping between application and machine graph
        """
        # pylint: disable=too-many-arguments, attribute-defined-outside-init

        # build file paths for reloaded stuff
        app_data_dir = generate_unique_folder_name(
            application_data_file_path, "reloaded_data_regions", "")
        if not os.path.exists(app_data_dir):
            os.makedirs(app_data_dir)

        report_dir = None
        if write_text_specs:
            report_dir = generate_unique_folder_name(
                report_directory, "reloaded_data_regions", "")
            if not os.path.exists(report_dir):
                os.makedirs(report_dir)

        application_vertices_to_reset = set()

        progress = ProgressBar(placements.n_placements, "Reloading data")
        for placement in progress.over(placements.placements):

            # Try to generate the data spec for the placement
            generated = self._regenerate_data_spec_for_vertices(
                placement, placement.vertex, transceiver, hostname, report_dir,
                write_text_specs, app_data_dir)

            # If the region was regenerated, mark it reloaded
            if generated:
                placement.vertex.mark_regions_reloaded()

            # If the spec wasn't generated directly, and there is an
            # application vertex, try with that
            if not generated and graph_mapper is not None:
                associated_vertex = graph_mapper.get_application_vertex(
                    placement.vertex)
                generated = self._regenerate_data_spec_for_vertices(
                    placement, associated_vertex, transceiver, hostname,
                    report_dir, write_text_specs, app_data_dir)

                # If the region was regenerated, remember the application
                # vertex for resetting later
                if generated:
                    application_vertices_to_reset.add(associated_vertex)

        # Only reset the application vertices here, otherwise only one
        # machine vertices data will be updated
        for vertex in application_vertices_to_reset:
            vertex.mark_regions_reloaded()

        # App data directory can be removed as should be empty
        os.rmdir(app_data_dir)

    def _regenerate_data_spec_for_vertices(
            self, placement, vertex, txrx, hostname, report_dir, write_text,
            app_data_dir):
        # If the vertex doesn't regenerate, skip
        if not isinstance(vertex, AbstractRewritesDataSpecification):
            return False

        # If the vertex doesn't require regeneration, skip
        if not vertex.requires_memory_regions_to_be_reloaded():
            return True

        # build the writers for the reports and data
        spec_file, spec = get_data_spec_and_file_writer_filename(
            placement.x, placement.y, placement.p, hostname,
            report_dir, write_text, app_data_dir)

        # Execute the regeneration
        vertex.regenerate_data_specification(spec, placement)

        # execute the spec
        with FileDataReader(spec_file) as spec_reader:
            data_spec_executor = DataSpecificationExecutor(
                spec_reader, SDRAM.max_sdram_found)
            data_spec_executor.execute()
        try:
            os.remove(spec_file)
        except Exception:  # pylint: disable=broad-except
            # Ignore the deletion of files as non-critical
            pass

        # Read the region table for the placement
        regions_base_address = txrx.get_cpu_information_from_core(
            placement.x, placement.y, placement.p).user[0]
        start_region = get_region_base_address_offset(regions_base_address, 0)
        table_size = get_region_base_address_offset(
            regions_base_address, MAX_MEM_REGIONS) - start_region
        offsets = REGION_STRUCT.unpack_from(
            txrx.read_memory(
                placement.x, placement.y, start_region, table_size))

        # Write the regions to the machine
        for i, region in enumerate(data_spec_executor.dsef.mem_regions):
            if region is not None and not region.unfilled:
                txrx.write_memory(
                    placement.x, placement.y, offsets[i],
                    region.region_data[:region.max_write_pointer])

        return True
