from data_specification.file_data_writer import FileDataWriter

from spinn_front_end_common.utilities import exceptions

from abc import ABCMeta
from six import add_metaclass
from abc import abstractmethod

import tempfile
import os
import threading

# used to stop file conflicts
_lock_condition = threading.Condition()


@add_metaclass(ABCMeta)
class AbstractDataSpecableVertex(object):
    """ A Vertex that enforces the methods for generating
       a dsg and gives some very basic impliemntation of a setup info method.
    """

    def __init__(self, machine_time_step, timescale_factor):
        self._machine_time_step = machine_time_step
        self._timescale_factor = timescale_factor
        self._application_runtime = None
        self._no_machine_time_steps = None

    def _write_basic_setup_info(self, spec, core_app_identifier, region_id):

        # Write this to the system region (to be picked up by the simulation):
        spec.switch_write_focus(region=region_id)
        spec.write_value(data=core_app_identifier)
        spec.write_value(data=self._machine_time_step * self._timescale_factor)
        spec.write_value(data=self._no_machine_time_steps)

    @abstractmethod
    def generate_data_spec(
            self, subvertex, placement, sub_graph, graph, routing_info,
            hostname, graph_subgraph_mapper, report_folder, ip_tags,
            reverse_ip_tags, write_text_specs, application_run_time_folder):
        """
        method to determine how to generate their data spec for a non neural
        application

        :param subvertex: the partitioned_vertex whcih this live packet gather
        is associated
        :param placement: the placement object associated with this
        partitioned vertex
        :param sub_graph: the partitioned_graph
        :param graph: the partitionable graph
        :param routing_info: the keys for this partitioned vertex
        :param hostname: the hostname associated with this spinnaker machine
        :param graph_subgraph_mapper: the mapper between the two graphs
        :param report_folder: where reports are to be written
        :param ip_tags: the lsit of iptags allcoated to the machine
        :param reverse_ip_tags: the list of reverse iptags allocated to the
        machine
        :param write_text_specs: boolean to write text specs
        :param application_run_time_folder: location where application data is
               stored.
        :return: Nothing
        """

    @abstractmethod
    def get_binary_file_name(self):
        """
        method to return the binary name for a given dataspecable vertex
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
        if self._no_machine_time_steps is None:
            self._no_machine_time_steps = new_no_machine_time_steps
        else:
            raise exceptions.ConfigurationException(
                "cannot set the number of machine time steps of a given"
                " model once it has already been set")

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

        # check if text reports are needed and if so initilise the report
        # writer to send down to dsg
        report_writer = None
        if write_text_specs:
            new_report_directory = os.path.join(report_directory,
                                                "data_spec_text_files")

            # uses locks to stop multiple instances of this writing the same
            # folder at the same time (os breaks down and throws exception
            # therwise)
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
        """
        helper method for isinstance
        :return:
        """
