from spinn_machine.utilities.progress_bar import ProgressBar

from spinn_front_end_common.abstract_models.\
    abstract_data_specable_vertex import AbstractDataSpecableVertex
from spinn_front_end_common.utilities.utility_objs.executable_targets import \
    ExecutableTargets
from spinn_front_end_common.utilities import exceptions


class FrontEndCommonPartitionableGraphDataSpecificationWriter(object):
    """ Executes a partitionable graph data specification generation
    """

    def __call__(
            self, placements, graph_mapper, tags, executable_finder,
            partitioned_graph, partitionable_graph, routing_infos, hostname,
            report_default_directory, write_text_specs,
            app_data_runtime_folder):
        """ generates the dsg for the graph.

        :return:
        """

        # iterate though subvertices and call generate_data_spec for each
        # vertex
        executable_targets = ExecutableTargets()
        dsg_targets = dict()

        # create a progress bar for end users
        progress_bar = ProgressBar(len(list(placements.placements)),
                                   "Generating data specifications")
        for placement in placements.placements:
            associated_vertex = graph_mapper.get_vertex_from_subvertex(
                placement.subvertex)

            self._generate_data_spec_for_subvertices(
                placement, associated_vertex, executable_targets, dsg_targets,
                graph_mapper, tags, executable_finder, partitioned_graph,
                partitionable_graph, routing_infos, hostname,
                report_default_directory, write_text_specs,
                app_data_runtime_folder)

            progress_bar.update()

        # finish the progress bar
        progress_bar.end()

        return {'executable_targets': executable_targets,
                'dsg_targets': dsg_targets}

    def _generate_data_spec_for_subvertices(
            self, placement, associated_vertex, executable_targets,
            dsg_targets, graph_mapper, tags, executable_finder,
            partitioned_graph, partitionable_graph, routing_infos, hostname,
            report_default_directory, write_text_specs,
            app_data_runtime_folder):

        # if the vertex can generate a DSG, call it
        if isinstance(associated_vertex, AbstractDataSpecableVertex):

            ip_tags = tags.get_ip_tags_for_vertex(
                placement.subvertex)
            reverse_ip_tags = tags.get_reverse_ip_tags_for_vertex(
                placement.subvertex)
            file_path = associated_vertex.generate_data_spec(
                placement.subvertex, placement, partitioned_graph,
                partitionable_graph, routing_infos, hostname, graph_mapper,
                report_default_directory, ip_tags, reverse_ip_tags,
                write_text_specs, app_data_runtime_folder)

            # link dsg file to subvertex
            dsg_targets[placement.x, placement.y, placement.p] = file_path

            # Get name of binary from vertex
            binary_name = associated_vertex.get_binary_file_name()

            # Attempt to find this within search paths
            binary_path = executable_finder.get_executable_path(
                binary_name)
            if binary_path is None:
                raise exceptions.ExecutableNotFoundException(binary_name)

            if not executable_targets.has_binary(binary_path):
                executable_targets.add_binary(binary_path)
            executable_targets.add_processor(
                binary_path, placement.x, placement.y, placement.p)
