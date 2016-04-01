from spinn_front_end_common.utilities import constants
from spinn_storage_handlers.file_data_writer import FileDataWriter

from abc import ABCMeta
from six import add_metaclass
from abc import abstractmethod

import hashlib
import tempfile
import os
import threading

# used to stop file conflicts
_lock_condition = threading.Condition()


@add_metaclass(ABCMeta)
class AbstractDataSpecableVertex(object):
    """ A Vertex that enforces the methods for generating a data specification\
        and gives some very basic implementation of a setup info method.
    """

    def __init__(self, machine_time_step, timescale_factor):
        self._machine_time_step = machine_time_step
        self._timescale_factor = timescale_factor
        self._no_machine_time_steps = None

    def _write_basic_setup_info(self, spec, region_id):

        # Hash application title
        application_name = os.path.splitext(self.get_binary_file_name())[0]

        # Get first 32-bits of the md5 hash of the application name
        application_name_hash = hashlib.md5(application_name).hexdigest()[:8]

        # Write this to the system region (to be picked up by the simulation):
        spec.switch_write_focus(region=region_id)
        spec.write_value(data=int(application_name_hash, 16))
        spec.write_value(data=self._machine_time_step * self._timescale_factor)

        # add SDP port number for receiving synchronisations and new run times
        spec.write_value(
            data=constants.SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value)

    @abstractmethod
    def generate_data_spec(
            self, subvertex, placement, sub_graph, graph, routing_info,
            hostname, graph_subgraph_mapper, report_folder, ip_tags,
            reverse_ip_tags, write_text_specs, application_run_time_folder):
        """ Generates the data specification of an application

        :param subvertex: the subvertex to generate data for
        :param placement: the placement of the subvertex
        :param sub_graph: the partitioned graph
        :param graph: the partitionable graph
        :param routing_info: the keys for this partitioned vertex
        :param hostname: the hostname associated with this spinnaker machine
        :param graph_subgraph_mapper: the mapper between the two graphs
        :param report_folder: where reports are to be written
        :param ip_tags: the list of iptags allocated to the machine
        :param reverse_ip_tags: the list of reverse ip tags allocated to the\
                    subvertex
        :param write_text_specs: boolean to write text specs
        :param application_run_time_folder: location where application data is\
                    stored.
        :return: iterable of file paths written
        """

    @abstractmethod
    def get_binary_file_name(self):
        """ Get the binary name to be run for subvertices of this vertex
        """

    @property
    def machine_time_step(self):
        """

        :return:
        """
        return self._machine_time_step

    @property
    def no_machine_time_steps(self):
        """

        :return:
        """
        return self._no_machine_time_steps

    def set_no_machine_time_steps(self, new_no_machine_time_steps):
        """

        :param new_no_machine_time_steps:
        :return:
        """
        self._no_machine_time_steps = new_no_machine_time_steps

    @staticmethod
    def get_data_spec_file_writers(
            processor_chip_x, processor_chip_y, processor_id, hostname,
            report_directory, write_text_specs,
            application_run_time_report_folder):
        """

        :param processor_chip_x:
        :param processor_chip_y:
        :param processor_id:
        :param hostname:
        :param report_directory:
        :param write_text_specs:
        :param application_run_time_report_folder:
        :return:
        """
        binary_file_path = \
            AbstractDataSpecableVertex.get_data_spec_file_path(
                processor_chip_x, processor_chip_y, processor_id, hostname,
                application_run_time_report_folder)
        data_writer = FileDataWriter(binary_file_path)

        # check if text reports are needed and if so initialise the report
        # writer to send down to dsg
        report_writer = None
        if write_text_specs:
            new_report_directory = os.path.join(report_directory,
                                                "data_spec_text_files")

            # uses locks to stop multiple instances of this writing the same
            # folder at the same time (os breaks down and throws exception
            # otherwise)
            _lock_condition.acquire()
            if not os.path.exists(new_report_directory):
                os.mkdir(new_report_directory)
            _lock_condition.release()

            file_name = "{}_dataSpec_{}_{}_{}.txt"\
                        .format(hostname, processor_chip_x, processor_chip_y,
                                processor_id)
            report_file_path = os.path.join(new_report_directory, file_name)
            report_writer = FileDataWriter(report_file_path)

        return data_writer, report_writer

    @staticmethod
    def get_data_spec_file_path(processor_chip_x, processor_chip_y,
                                processor_id, hostname,
                                application_run_time_folder):
        """
        :param processor_chip_x:
        :param processor_chip_y:
        :param processor_id:
        :param hostname:
        :param application_run_time_folder:
        :return:
        """

        if application_run_time_folder == "TEMP":
            application_run_time_folder = tempfile.gettempdir()

        binary_file_path = \
            application_run_time_folder + os.sep + "{}_dataSpec_{}_{}_{}.dat"\
            .format(hostname, processor_chip_x, processor_chip_y, processor_id)
        return binary_file_path

    @staticmethod
    def get_application_data_file_path(
            processor_chip_x, processor_chip_y, processor_id, hostname,
            application_run_time_folder):
        """

        :param processor_chip_x:
        :param processor_chip_y:
        :param processor_id:
        :param hostname:
        :param application_run_time_folder:
        :return:
        """

        if application_run_time_folder == "TEMP":
            application_run_time_folder = tempfile.gettempdir()

        application_data_file_name = application_run_time_folder + os.sep + \
            "{}_appData_{}_{}_{}.dat".format(hostname, processor_chip_x,
                                             processor_chip_y, processor_id)
        return application_data_file_name

    @abstractmethod
    def is_data_specable(self):
        """ Helper method for isinstance
        :return:
        """
