"""
FrontEndCommonPartitionableGraphApplicationLoader
"""

from pacman.utilities.utility_objs.progress_bar import ProgressBar

from spinnman.data.file_data_reader import FileDataReader \
    as SpinnmanFileDataReader

import logging

logger = logging.getLogger(__name__)


class FrontEndCommonPartitionableGraphApplicationLoader(object):
    """
    """

    def __call__(
            self, processor_to_app_data_base_address, transceiver,
            placement_to_app_data_files, verify=False):

        # go through the placements and see if there's any application data to
        # load
        progress_bar = ProgressBar(len(placement_to_app_data_files),
                                   "Loading application data onto the machine")
        for (x, y, p, label) in placement_to_app_data_files:
            logger.debug(
                "loading application data for vertex {}".format(label))
            key = (x, y, p, label)
            start_address = \
                processor_to_app_data_base_address[key]['start_address']
            memory_written = \
                processor_to_app_data_base_address[key]['memory_written']

            application_file_paths = placement_to_app_data_files[key]

            for file_path_for_application_data in application_file_paths:
                application_data_file_reader = SpinnmanFileDataReader(
                    file_path_for_application_data)
                logger.debug(
                    "writing application data for vertex {}".format(label))
                transceiver.write_memory(
                    x, y, start_address, application_data_file_reader,
                    memory_written)
                application_data_file_reader.close()

                if verify:
                    application_data_file_reader = SpinnmanFileDataReader(
                        file_path_for_application_data)
                    all_data = application_data_file_reader.readall()
                    read_data = transceiver.read_memory(
                        x, y, start_address, memory_written)
                    if read_data != all_data:
                        raise Exception("Miswrite of {}, {}, {}, {}"
                                        .format(x, y, p, start_address))
                    application_data_file_reader.close()

                # update user 0 so that it points to the start of the
                # applications data region on sdram
                logger.debug(
                    "writing user 0 address for vertex {}".format(label))
                user_o_register_address = \
                    transceiver.get_user_0_register_address_from_core(x, y, p)
                transceiver.write_memory(
                    x, y, user_o_register_address, start_address)
            progress_bar.update()
        progress_bar.end()

        return {"LoadedApplicationDataToken": True}
