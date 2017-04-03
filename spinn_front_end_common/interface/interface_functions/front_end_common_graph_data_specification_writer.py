from data_specification import utility_calls

from spinn_machine.utilities.progress_bar import ProgressBar

from spinn_front_end_common.abstract_models.\
    abstract_generates_data_specification import \
    AbstractGeneratesDataSpecification
from spinn_front_end_common.utilities import exceptions

from collections import defaultdict


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
            self, placements, hostname,
            report_default_directory, write_text_specs,
            app_data_runtime_folder, machine, graph_mapper=None):
        """

        :param placements: placements of machine graph to cores
        :param hostname: spinnaker machine name
        :param report_default_directory: the location where reports are stored
        :param write_text_specs:\
            True if the textual version of the specification is to be written
        :param app_data_runtime_folder:\
            Folder where data specifications should be written to
        :param machine: the python representation of the spinnaker machine
        :param graph_mapper:\
            the mapping between application and machine graph

        :return: dsg targets (map of placement tuple and filename)
        """

        # iterate though vertices and call generate_data_spec for each
        # vertex
        dsg_targets = dict()

        progress_bar = ProgressBar(
            placements.n_placements, "Generating data specifications")
        for placement in placements.placements:

            # Try to generate the data spec for the placement
            generated = self._generate_data_spec_for_vertices(
                placement, placement.vertex, dsg_targets, hostname,
                report_default_directory, write_text_specs,
                app_data_runtime_folder, machine)

            # If the spec wasn't generated directly, and there is an
            # application vertex, try with that
            if not generated and graph_mapper is not None:
                associated_vertex = graph_mapper.get_application_vertex(
                    placement.vertex)
                self._generate_data_spec_for_vertices(
                    placement, associated_vertex, dsg_targets, hostname,
                    report_default_directory, write_text_specs,
                    app_data_runtime_folder, machine)
            progress_bar.update()
        progress_bar.end()

        return dsg_targets

    def _generate_data_spec_for_vertices(
            self, placement, vertex, dsg_targets, hostname,
            report_default_directory, write_text_specs,
            app_data_runtime_folder, machine):
        """

        :param placements: placements of machine graph to cores
        :param vertex: the specific vertex to write dsg for.
        :param hostname: spinnaker machine name
        :param report_default_directory: the location where reports are stored
        :param write_text_specs:\
            True if the textual version of the specification is to be written
        :param app_data_runtime_folder: \
            Folder where data specifications should be written to
        :param machine: the python representation of the spinnaker machine
        :param graph_mapper: the mapping between application and machine graph
        :return: True if the vertex was data specable, False otherwise
        """

        # if the vertex can generate a DSG, call it
        if not isinstance(vertex, AbstractGeneratesDataSpecification):
            return False

        # build the writers for the reports and data
        data_writer_filename, spec = \
            utility_calls.get_data_spec_and_file_writer_filename(
                placement.x, placement.y, placement.p, hostname,
                report_default_directory,
                write_text_specs, app_data_runtime_folder)

        # link dsg file to vertex
        dsg_targets[placement.x, placement.y, placement.p] = \
            data_writer_filename

        # generate the dsg file
        vertex.generate_data_specification(spec, placement)

        # Check the memory usage
        self._region_sizes[placement.vertex] = spec.region_sizes
        self._vertices_by_chip[placement.x, placement.y].append(
            placement.vertex)
        self._sdram_usage[placement.x, placement.y] += sum(
            spec.region_sizes)
        if (self._sdram_usage[placement.x, placement.y] <=
                machine.get_chip_at(placement.x, placement.y).sdram.size):
            return True

        # creating the error message which contains the memory usage of
        #  what each core within the chip uses and its original
        # estimate.
        memory_usage = "\n".join([
            "    {}: {} (total={}, estimated={})".format(
                vert, self._region_sizes[vert],
                sum(self._region_sizes[vert]),
                vert.resources_required.sdram.get_value())
            for vert in self._vertices_by_chip[
                placement.x, placement.y]])

        raise exceptions.ConfigurationException(
            "Too much SDRAM has been used on {}, {}.  Vertices and"
            " their usage on that chip is as follows:\n{}".format(
                placement.x, placement.y, memory_usage))
