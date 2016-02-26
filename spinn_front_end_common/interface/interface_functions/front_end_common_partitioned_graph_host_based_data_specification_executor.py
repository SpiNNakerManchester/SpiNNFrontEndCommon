from pacman.utilities.utility_objs.progress_bar import ProgressBar

from spinn_front_end_common.abstract_models.\
    abstract_data_specable_vertex import \
    AbstractDataSpecableVertex
from spinn_front_end_common.utilities import exceptions as front_end_exceptions

from spinnaker_graph_front_end.\
    abstract_partitioned_data_specable_vertex import \
    AbstractPartitionedDataSpecableVertex

from data_specification.data_specification_executor import \
    DataSpecificationExecutor

from spinn_storage_handlers.file_data_reader import FileDataReader
from spinn_storage_handlers.file_data_writer import FileDataWriter
from data_specification import exceptions

import os
import logging

logger = logging.getLogger(__name__)


class FrontEndCommonPartitionedGraphHostBasedDataSpecificationExecutor(
        object):
    """
    FrontEndCommonPartitionedGraphHostBasedDataSpecificationExecutor
    """

    def __call__(self, placements, report_default_directory,
                 hostname, application_data_runtime_folder, machine,
                 dsg_targets, write_text_specs):
        """
        :param hostname:
        :param placements:
        :param graph_mapper:
        :param write_text_specs:
        :param application_data_runtime_folder:
        :return:
        """
        next_position_tracker = dict()
        space_available_tracker = dict()
        processor_to_app_data_base_address = dict()
        placement_to_application_data_files = dict()

        # create a progress bar for end users
        progress_bar = ProgressBar(len(list(placements.placements)),
                                   "Executing data specifications")

        for placement in placements.placements:
            associated_vertex = placement.subvertex

            # if the vertex can generate a DSG, call it
            if (isinstance(associated_vertex, AbstractDataSpecableVertex) or
                    isinstance(
                        associated_vertex,
                        AbstractPartitionedDataSpecableVertex)):

                placement_to_application_data_files[
                    (placement.x, placement.y, placement.p,
                     associated_vertex.label)] = list()
                data_spec_file_paths = dsg_targets[placement.subvertex]
                for data_spec_file_path in data_spec_file_paths:
                    app_data_file_path = \
                        associated_vertex.get_application_data_file_path(
                            placement.x, placement.y, placement.p, hostname,
                            application_data_runtime_folder)

                    # update application data file path tracker
                    placement_to_application_data_files[
                        (placement.x, placement.y, placement.p,
                         associated_vertex.label)].append(
                        app_data_file_path)

                    # build writers
                    data_spec_reader = FileDataReader(data_spec_file_path)
                    data_writer = FileDataWriter(app_data_file_path)

                    # locate current memory requirement
                    chip = machine.get_chip_at(placement.x, placement.y)
                    next_position = chip.sdram.user_base_address
                    space_available = chip.sdram.size
                    placement_key = (placement.x, placement.y)
                    if placement_key in next_position_tracker:
                        next_position = next_position_tracker[placement_key]
                        space_available = \
                            space_available_tracker[placement_key]

                    # generate a file writer for DSE report (app pointer table)
                    report_writer = None
                    if write_text_specs:
                        new_report_directory = os.path.join(
                            report_default_directory, "data_spec_text_files")

                        if not os.path.exists(new_report_directory):
                            os.mkdir(new_report_directory)

                        file_name = "{}_DSE_report_for_{}_{}_{}.txt".format(
                            hostname, placement.x, placement.y, placement.p)
                        report_file_path = os.path.join(new_report_directory,
                                                        file_name)
                        report_writer = FileDataWriter(report_file_path)

                    # generate data spec executor
                    host_based_data_spec_executor = DataSpecificationExecutor(
                        data_spec_reader, data_writer, space_available,
                        report_writer)

                    # update memory calculation and run data spec executor
                    bytes_used_by_spec = 0
                    bytes_written_by_spec = 0
                    try:
                        bytes_used_by_spec, bytes_written_by_spec = \
                            host_based_data_spec_executor.execute()
                    except exceptions.DataSpecificationException as e:
                        logger.error(
                            "Error executing data specification for {} "
                            "with the issue of {}"
                            .format(associated_vertex, e.message))
                        raise front_end_exceptions.RallocException(
                            "Error executing data specification for {} "
                            "with the issue of {}"
                            .format(associated_vertex, e.message))

                    # update base address mapper
                    processor_mapping_key = \
                        (placement.x, placement.y, placement.p,
                         associated_vertex.label)

                    processor_to_app_data_base_address[
                        processor_mapping_key] = {
                            'start_address': next_position,
                            'memory_used': bytes_used_by_spec,
                            'memory_written': bytes_written_by_spec}

                    next_position_tracker[placement_key] = (next_position +
                                                            bytes_used_by_spec)
                    space_available_tracker[placement_key] = \
                        (space_available - bytes_used_by_spec)

            # update the progress bar
            progress_bar.update()

        # close the progress bar
        progress_bar.end()
        return {'processor_to_app_data_base_address':
                processor_to_app_data_base_address,
                'placement_to_app_data_files':
                placement_to_application_data_files}
