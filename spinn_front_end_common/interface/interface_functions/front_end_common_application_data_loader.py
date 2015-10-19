"""

"""

from pacman.utilities.utility_objs.progress_bar import ProgressBar

from spinn_front_end_common.abstract_models.\
    abstract_data_specable_vertex import AbstractDataSpecableVertex

from spinnman.data.file_data_reader import FileDataReader \
    as SpinnmanFileDataReader

import logging

logger = logging.getLogger(__name__)


class FrontEndCmmonApplicationLoader(object):
    """

    """

    def __call__(
            self, placements, vertex_to_subvertex_mapper,
            processor_to_app_data_base_address, transciever,
            vertex_to_app_data_files, verify=False):

        # go through the placements and see if there's any application data to
        # load
        progress_bar = ProgressBar(len(list(placements.placements)),
                                   "Loading application data onto the machine")
        for placement in placements.placements:
            associated_vertex = \
                vertex_to_subvertex_mapper.get_vertex_from_subvertex(
                    placement.subvertex)

            if isinstance(associated_vertex, AbstractDataSpecableVertex):
                logger.debug("loading application data for vertex {}"
                             .format(associated_vertex.label))
                key = (placement.x, placement.y, placement.p)
                start_address = \
                    processor_to_app_data_base_address[key]['start_address']
                memory_written = \
                    processor_to_app_data_base_address[key]['memory_written']

                application_file_paths = \
                    vertex_to_app_data_files[placement.subvertex]

                for file_path_for_application_data in application_file_paths:
                    application_data_file_reader = SpinnmanFileDataReader(
                        file_path_for_application_data)
                    logger.debug("writing application data for vertex {}"
                                 .format(associated_vertex.label))
                    transciever.write_memory(
                        placement.x, placement.y, start_address,
                        application_data_file_reader, memory_written)
                    application_data_file_reader.close()

                    if verify:
                        application_data_file_reader = SpinnmanFileDataReader(
                            file_path_for_application_data)
                        all_data = application_data_file_reader.readall()
                        read_data = transciever.read_memory(
                            placement.x, placement.y, start_address,
                            memory_written)
                        if read_data != all_data:
                            raise Exception(
                                "Miswrite of {}, {}, {}, {}".format(
                                    placement.x, placement.y, placement.p,
                                    start_address))
                        application_data_file_reader.close()

                    # update user 0 so that it points to the start of the
                    # applications data region on sdram
                    logger.debug("writing user 0 address for vertex {}"
                                 .format(associated_vertex.label))
                    user_o_register_address = \
                        transciever.get_user_0_register_address_from_core(
                            placement.x, placement.y, placement.p)
                    transciever.write_memory(
                        placement.x, placement.y, user_o_register_address,
                        start_address)
            progress_bar.update()
        progress_bar.end()

        return {"LoadedApplicationDataToken": True}
