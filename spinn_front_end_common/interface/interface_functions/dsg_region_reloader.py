from spinn_utilities.progress_bar import ProgressBar
from spinn_machine import SDRAM

from data_specification import DataSpecificationExecutor
from data_specification import utility_calls
from data_specification.constants import MAX_MEM_REGIONS

from spinn_front_end_common.abstract_models \
    import AbstractRewritesDataSpecification
from spinn_front_end_common.utilities import helpful_functions

from spinn_storage_handlers import FileDataReader

import os
import struct


class DSGRegionReloader(object):
    """ Regenerates Data Specifications
    """

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

        # build file paths for reloaded stuff
        reloaded_dsg_data_files_file_path = \
            helpful_functions.generate_unique_folder_name(
                application_data_file_path, "reloaded_data_regions", "")
        reloaded_dsg_report_files_file_path = \
            helpful_functions.generate_unique_folder_name(
                report_directory, "reloaded_data_regions", "")

        # build new folders
        if not os.path.exists(reloaded_dsg_data_files_file_path):
            os.makedirs(reloaded_dsg_data_files_file_path)
        if not os.path.exists(reloaded_dsg_report_files_file_path):
            os.makedirs(reloaded_dsg_report_files_file_path)

        application_vertices_to_reset = set()

        progress = ProgressBar(placements.n_placements, "Reloading data")
        for placement in progress.over(placements.placements):

            # Try to generate the data spec for the placement
            generated = self._regenerate_data_spec_for_vertices(
                transceiver, placement, placement.vertex, hostname,
                reloaded_dsg_report_files_file_path, write_text_specs,
                reloaded_dsg_data_files_file_path)

            # If the region was regenerated, mark it reloaded
            if generated:
                placement.vertex.mark_regions_reloaded()

            # If the spec wasn't generated directly, and there is an
            # application vertex, try with that
            if not generated and graph_mapper is not None:
                associated_vertex = graph_mapper.get_application_vertex(
                    placement.vertex)
                generated = self._regenerate_data_spec_for_vertices(
                    transceiver, placement, associated_vertex, hostname,
                    reloaded_dsg_report_files_file_path, write_text_specs,
                    reloaded_dsg_data_files_file_path)

                # If the region was regenerated, remember the application
                # vertex for resetting later
                if generated:
                    application_vertices_to_reset.add(associated_vertex)

        # Only reset the application vertices here, otherwise only one
        # machine vertices data will be updated
        for vertex in application_vertices_to_reset:
            vertex.mark_regions_reloaded()

    @staticmethod
    def _regenerate_data_spec_for_vertices(
            transceiver, placement, vertex, hostname,
            reloaded_dsg_report_files_file_path, write_text_specs,
            reloaded_dsg_data_files_file_path):

        # If the vertex doesn't regenerate, skip
        if not isinstance(vertex, AbstractRewritesDataSpecification):
            return False

        # If the vertex doesn't require regeneration, skip
        if not vertex.requires_memory_regions_to_be_reloaded():
            return True

        # build the writers for the reports and data
        spec_file, spec = utility_calls.get_data_spec_and_file_writer_filename(
            placement.x, placement.y, placement.p, hostname,
            reloaded_dsg_report_files_file_path,
            write_text_specs, reloaded_dsg_data_files_file_path)

        # Execute the regeneration
        vertex.regenerate_data_specification(spec, placement)

        # execute the spec
        spec_reader = FileDataReader(spec_file)
        data_spec_executor = DataSpecificationExecutor(
            spec_reader, SDRAM.DEFAULT_SDRAM_BYTES)
        data_spec_executor.execute()

        # Read the region table for the placement
        regions_base_address = transceiver.get_cpu_information_from_core(
            placement.x, placement.y, placement.p).user[0]
        start_region = utility_calls.get_region_base_address_offset(
            regions_base_address, 0)
        table_size = utility_calls.get_region_base_address_offset(
            regions_base_address, MAX_MEM_REGIONS) - start_region
        offsets = struct.unpack_from(
            "<{}I".format(MAX_MEM_REGIONS),
            transceiver.read_memory(
                placement.x, placement.y, start_region, table_size))

        # Write the regions to the machine
        for i, region in enumerate(data_spec_executor.dsef.mem_regions):
            if region is not None and not region.unfilled:
                transceiver.write_memory(
                    placement.x, placement.y, offsets[i],
                    region.region_data[:region.max_write_pointer])

        return True
