
# data spec imports
from data_specification.data_specification_executor import \
    DataSpecificationExecutor
from data_specification.file_data_reader import FileDataReader
from data_specification.file_data_writer import FileDataWriter
from data_specification import exceptions
import data_specification.data_spec_sender.spec_sender as spec_sender

# pacman imports
from pacman.utilities.utility_objs.progress_bar import ProgressBar

# spinnman imports
from spinnman.model.core_subsets import CoreSubsets
from spinnman.data.file_data_reader import FileDataReader as \
    SpinnmanFileDataReader
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.sdp.sdp_message import SDPMessage

# front end common imports
from spinn_front_end_common.abstract_models.\
    abstract_data_specable_vertex import \
    AbstractDataSpecableVertex
from spinn_front_end_common.utilities import constants

import os
import logging
import struct
import time

logger = logging.getLogger(__name__)


class FrontEndCommonPartitionableGraphMachineExecuteDataSpecification(object):
    """ Executes the machine based data specification
    """

    def __call__(
            self, hostname, placements, graph_mapper, report_default_directory,
            write_text_specs, runtime_application_data_folder, machine,
            board_version, dsg_targets, transceiver):
        """

        :param hostname:
        :param placements:
        :param graph_mapper:
        :param write_text_specs:
        :param runtime_application_data_folder:
        :param machine:
        :return:
        """
        data = self.spinnaker_based_data_specification_execution(
            hostname, placements, graph_mapper, write_text_specs,
            runtime_application_data_folder, machine, board_version,
            report_default_directory, dsg_targets, transceiver)

        return data

    def spinnaker_based_data_specification_execution(
            self, hostname, placements, graph_mapper, write_text_specs,
            application_data_runtime_folder, machine, board_version,
            report_default_directory, dsg_targets, transceiver):
        """

        :param hostname:
        :param placements:
        :param graph_mapper:
        :param write_text_specs:
        :param application_data_runtime_folder:
        :param machine:
        :return:
        """
        # check which cores are in use
        core_subset = CoreSubsets()
        for placement in placements.placements:
            core_subset.add_processor(placement.x, placement.y, placement.p)

        # read DSE exec name
        executable_targets = {
            os.path.dirname(spec_sender.__file__) +
            '/data_specification_executor.aplx': core_subset}

        self._load_executable_images(
            transceiver, executable_targets, 31,
            app_data_folder=application_data_runtime_folder)

        # create a progress bar for end users
        progress_bar = ProgressBar(len(list(placements.placements)),
                                   "on executing data specifications on chip")

        for placement in placements.placements:
            associated_vertex = graph_mapper.get_vertex_from_subvertex(
                placement.subvertex)

            # if the vertex can generate a DSG, call it
            if isinstance(associated_vertex, AbstractDataSpecableVertex):

                data_spec_file_path = \
                            associated_vertex.get_data_spec_file_path(
                                placement.x, placement.y, placement.p, hostname,
                                application_data_runtime_folder)

                data_spec_file_size = os.path.getsize(data_spec_file_path)

                header = SDPHeader(flags = SDPFlag.REPLY_NOT_EXPECTED,
                                   destination_cpu    = placement.p,
                                   destination_chip_x = placement.x,
                                   destination_chip_y = placement.y,
                                   destination_port   = 1)

                # Wait for the core to get into the READY_TO_RECEIVE state.
                while transceiver.get_cpu_information_from_core(
                        placement.x, placement.y, placement.p).user[1] != 0x1:
                    time.sleep(0.01)

                # Send a packet containing the length of the data (the
                # length of the internal buffer).
                msg_data_len = struct.pack("<I", data_spec_file_size)

                transceiver.send_sdp_message(SDPMessage(header,
                                                             msg_data_len))

                # Wait for the core to get into the WAITING_FOR_DATA state.
                return_wait_state = transceiver.get_cpu_information_from_core(
                    placement.x, placement.y, placement.p).user[1]
                while return_wait_state != 0x2:
                    transceiver.send_sdp_message(SDPMessage(header,
                                                             msg_data_len))
                    return_wait_state = transceiver.get_cpu_information_from_core(
                        placement.x, placement.y, placement.p).user[1]
                    print "waiting", return_wait_state
                    time.sleep(1)


                # Write data at the address pointed at by user2.
                destination_address = \
                    transceiver. get_cpu_information_from_core(
                        placement.x, placement.y, placement.p).user[2]

                application_data_file_reader = SpinnmanFileDataReader(
                    data_spec_file_path)
                logger.debug("writing application data for vertex {}"
                             .format(associated_vertex.label))
                transceiver.write_memory(
                    placement.x, placement.y, destination_address,
                    application_data_file_reader, data_spec_file_size)


                # Send a packet that triggers the execution of the data specification.
                transceiver.send_sdp_message(SDPMessage(
                    header,struct.pack("<I", 0)))



                #fileReader = FileDataReader(data_spec_file_path)

                #sender     = SpecSender(transceiver, placement)

                #dataSpecSender = DataSpecificationSender(fileReader, sender)
                #dataSpecSender.sendSpec()
                progress_bar.update()
        progress_bar.end()

        # What needs to be returned???
        return {"LoadedApplicationDataToken": True}
        #return {'processor_to_app_data_base_address':
        #        processor_to_app_data_base_address,
        #        'placement_to_app_data_files':
        #        placement_to_application_data_files}

    def _load_executable_images(self, transceiver, executable_targets, app_id,
                                app_data_folder):
        """ Go through the executable targets and load each binary to \
            everywhere and then send a start request to the cores that \
            actually use it
        """
        #if self._reports_states.transciever_report:
        #    reports.re_load_script_load_executables_init(
        #        app_data_folder, executable_targets)

        progress_bar = ProgressBar(len(executable_targets),
                                   "Loading executables onto the machine")
        for executable_target_key in executable_targets:
            file_reader = SpinnmanFileDataReader(executable_target_key)
            core_subset = executable_targets[executable_target_key]

            statinfo = os.stat(executable_target_key)
            size = statinfo.st_size

            # TODO there is a need to parse the binary and see if its
            # ITCM and DTCM requirements are within acceptable params for
            # operating on spinnaker. Currnently there jsut a few safety
            # checks which may not be accurate enough.
            if size > constants.MAX_SAFE_BINARY_SIZE:
                logger.warn(
                    "The size of this binary is large enough that its"
                    " possible that the binary may be larger than what is"
                    " supported by spinnaker currently. Please reduce the"
                    " binary size if it starts to behave strangely, or goes"
                    " into the wdog state before starting.")
                if size > constants.MAX_POSSIBLE_BINARY_SIZE:
                    raise exceptions.ConfigurationException(
                        "The size of the binary is too large and therefore"
                        " will very likely cause a WDOG state. Until a more"
                        " precise measurement of ITCM and DTCM can be produced"
                        " this is deemed as an error state. Please reduce the"
                        " size of your binary or circumvent this error check.")

            transceiver.execute_flood(core_subset, file_reader, app_id,
                                     size)

#            if self._reports_states.transciever_report:
#                reports.re_load_script_load_executables_individual(
#                    app_data_folder, executable_target_key,
#                    app_id, size)
            progress_bar.update()
        progress_bar.end()
