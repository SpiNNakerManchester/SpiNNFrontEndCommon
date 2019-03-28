try:
    from collections.abc import defaultdict
except ImportError:
    from collections import defaultdict
from spinn_utilities.progress_bar import ProgressBar
from data_specification import DataSpecificationGenerator
from data_specification.utility_calls import (
    get_report_writer)
from spinn_front_end_common.abstract_models import (
    AbstractRewritesDataSpecification, AbstractGeneratesDataSpecification)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.interface.ds.data_specification_targets import \
    DataSpecificationTargets


class GraphDataSpecificationWriter(object):
    """ Executes the data specification generation step.
    """

    __slots__ = (
        # Dict of SDRAM usage by chip coordinates
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
            machine, graph_mapper=None, placement_order=None):
        """
        :param placements: placements of machine graph to cores
        :param hostname: SpiNNaker machine name
        :param report_default_directory: the location where reports are stored
        :param write_text_specs:\
            True if the textual version of the specification is to be written
        :param machine: the python representation of the SpiNNaker machine
        :param graph_mapper:\
            the mapping between application and machine graph
        :param placement:\
            the optional order in which placements should be examined

        :return: DSG targets (map of placement tuple and filename)
        """
        # pylint: disable=too-many-arguments

        # iterate though vertices and call generate_data_spec for each
        # vertex
        dsg_targets = DataSpecificationTargets(
            machine, report_default_directory)

        if placement_order is None:
            placement_order = placements.placements

        progress = ProgressBar(
            placements.n_placements, "Generating data specifications")
        vertices_to_reset = list()
        for placement in progress.over(placement_order):
            # Try to generate the data spec for the placement
            generated = self._generate_data_spec_for_vertices(
                placement, placement.vertex, dsg_targets, hostname,
                report_default_directory, write_text_specs, machine)

            if generated and isinstance(
                    placement.vertex, AbstractRewritesDataSpecification):
                vertices_to_reset.append(placement.vertex)

            # If the spec wasn't generated directly, and there is an
            # application vertex, try with that
            if not generated and graph_mapper is not None:
                associated_vertex = graph_mapper.get_application_vertex(
                    placement.vertex)
                generated = self._generate_data_spec_for_vertices(
                    placement, associated_vertex, dsg_targets, hostname,
                    report_default_directory, write_text_specs, machine)
                if generated and isinstance(
                        associated_vertex, AbstractRewritesDataSpecification):
                    vertices_to_reset.append(associated_vertex)

        # Ensure that the vertices know their regions have been reloaded
        for vertex in vertices_to_reset:
            vertex.mark_regions_reloaded()

        return dsg_targets

    def _generate_data_spec_for_vertices(
            self, placement, vertex, dsg_targets, hostname,
            report_default_directory, write_text_specs, machine):
        """
        :param placement: placement of machine graph to cores
        :param vertex: the specific vertex to write DSG for.
        :param hostname: SpiNNaker machine name
        :param report_default_directory: the location where reports are stored
        :param write_text_specs:\
            True if the textual version of the specification is to be written
        :param machine: the python representation of the SpiNNaker machine
        :return: True if the vertex was data spec-able, False otherwise
        :rtype: bool
        """
        # pylint: disable=too-many-arguments

        # if the vertex can generate a DSG, call it
        if not isinstance(vertex, AbstractGeneratesDataSpecification):
            return False

        with dsg_targets.create_data_spec(
                placement.x, placement.y, placement.p) as data_writer:

            report_writer = get_report_writer(
                placement.x, placement.y, placement.p, hostname,
                report_default_directory, write_text_specs)
            spec = DataSpecificationGenerator(data_writer, report_writer)

            # generate the DSG file
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
        memory_usage = "\n".join((
            "    {}: {} (total={}, estimated={})".format(
                vert, self._region_sizes[vert],
                sum(self._region_sizes[vert]),
                vert.resources_required.sdram.get_value())
            for vert in self._vertices_by_chip[placement.x, placement.y]))

        raise ConfigurationException(
            "Too much SDRAM has been used on {}, {}.  Vertices and"
            " their usage on that chip is as follows:\n{}".format(
                placement.x, placement.y, memory_usage))
