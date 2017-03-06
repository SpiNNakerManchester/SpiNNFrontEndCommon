from data_specification.data_specification_generator import \
    DataSpecificationGenerator
from pacman.model.graphs.application.impl.application_graph import \
    ApplicationGraph
from pacman.model.graphs.machine.impl.machine_graph import MachineGraph
from spinn_machine.utilities.progress_bar import ProgressBar

from spinn_front_end_common.abstract_models.\
    abstract_generates_data_specification import \
    AbstractGeneratesDataSpecification

import tempfile
import os
import threading

# used to stop file conflicts
from spinn_storage_handlers.file_data_writer import FileDataWriter
from collections import defaultdict
from spinn_front_end_common.utilities import exceptions

_lock_condition = threading.Condition()


class FrontEndCommonGraphDataSpecificationWriter(object):
    """ Executes data specification generation
    """

    __slots__ = (

        # Dict of sdram usage by chip coordinates
        "_sdram_usage",

        # Dict of list of region sizes by vertex
        "_region_sizes",

        # Dict of list of vertices by chip coordinates
        "_vertices_by_chip"
    )

    def __init__(self):
        self._sdram_usage = defaultdict(lambda: 0)
        self._region_sizes = dict()
        self._vertices_by_chip = defaultdict(list)

    def __call__(
            self, placements, graph, hostname,
            report_default_directory, write_text_specs,
            app_data_runtime_folder, machine, graph_mapper=None):
        """ generates the dsg for the graph.

        """

        # iterate though vertices and call generate_data_spec for each
        # vertex
        dsg_targets = dict()

        if isinstance(graph, ApplicationGraph):
            progress_bar = ProgressBar(len(list(placements.placements)),
                                       "Generating data specifications")
            for placement in placements.placements:
                associated_vertex = graph_mapper.get_application_vertex(
                    placement.vertex)
                self._generate_data_spec_for_vertices(
                    placement, associated_vertex, dsg_targets, hostname,
                    report_default_directory, write_text_specs,
                    app_data_runtime_folder, machine)
                progress_bar.update()
            progress_bar.end()
        elif isinstance(graph, MachineGraph):
            progress_bar = ProgressBar(
                graph.n_vertices, "Generating data specifications")
            for vertex in graph.vertices:
                placement = placements.get_placement_of_vertex(vertex)
                self._generate_data_spec_for_vertices(
                    placement, vertex, dsg_targets, hostname,
                    report_default_directory, write_text_specs,
                    app_data_runtime_folder, machine)
                progress_bar.update()
            progress_bar.end()

        return dsg_targets

    def _generate_data_spec_for_vertices(
            self, placement, associated_vertex, dsg_targets, hostname,
            report_default_directory, write_text_specs,
            app_data_runtime_folder, machine):

        # if the vertex can generate a DSG, call it
        if isinstance(associated_vertex, AbstractGeneratesDataSpecification):

            # build the writers for the reports and data
            data_writer, report_writer = \
                self.get_data_spec_file_writers(
                    placement.x, placement.y, placement.p, hostname,
                    report_default_directory,
                    write_text_specs, app_data_runtime_folder)

            # build the file writer for the spec
            spec = DataSpecificationGenerator(data_writer, report_writer)

            # generate the dsg file
            associated_vertex.generate_data_specification(spec, placement)
            data_writer.close()

            # Check the memory usage
            self._region_sizes[placement.vertex] = spec.region_sizes
            self._vertices_by_chip[placement.x, placement.y].append(
                placement.vertex)
            self._sdram_usage[placement.x, placement.y] += sum(
                spec.region_sizes)
            if (self._sdram_usage[placement.x, placement.y] >
                    machine.get_chip_at(placement.x, placement.y).sdram.size):

                # creating the error message which contains the memory usage of
                #  what each core within the chip uses and its original
                # estimate.
                memory_usage = "\n".join([
                    "    {}: {} (total={}, estimated={})".format(
                        vertex, self._region_sizes[vertex],
                        sum(self._region_sizes[vertex]),
                        vertex.resources_required.sdram.get_value())
                    for vertex in self._vertices_by_chip[
                        placement.x, placement.y]])

                raise exceptions.ConfigurationException(
                    "Too much SDRAM has been used on {}, {}.  Vertices and"
                    " their usage on that chip is as follows:\n{}".format(
                        placement.x, placement.y, memory_usage))

            # link dsg file to vertex
            dsg_targets[placement.x, placement.y, placement.p] = \
                data_writer.filename

    def get_data_spec_file_writers(
            self, processor_chip_x, processor_chip_y, processor_id,
            hostname,
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
        """

        binary_file_path = self.get_data_spec_file_path(
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

            file_name = "{}_dataSpec_{}_{}_{}.txt" \
                .format(hostname, processor_chip_x, processor_chip_y,
                        processor_id)
            report_file_path = os.path.join(new_report_directory, file_name)
            report_writer = FileDataWriter(report_file_path)

        return data_writer, report_writer

    @staticmethod
    def get_data_spec_file_path(processor_chip_x, processor_chip_y,
                                processor_id, hostname,
                                application_run_time_folder):
        if application_run_time_folder == "TEMP":
            application_run_time_folder = tempfile.gettempdir()

        binary_file_path = (
            application_run_time_folder + os.sep +
            "{}_dataSpec_{}_{}_{}.dat".format(
                hostname, processor_chip_x, processor_chip_y, processor_id))
        return binary_file_path

    @staticmethod
    def get_application_data_file_path(
            processor_chip_x, processor_chip_y, processor_id, hostname,
            application_run_time_folder):
        if application_run_time_folder == "TEMP":
            application_run_time_folder = tempfile.gettempdir()

        application_data_file_name = \
            application_run_time_folder + os.sep + \
            "{}_appData_{}_{}_{}.dat".format(
                hostname, processor_chip_x, processor_chip_y, processor_id)
        return application_data_file_name
