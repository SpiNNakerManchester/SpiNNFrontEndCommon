from spinn_utilities.progress_bar import ProgressBar
from spinn_front_end_common.interface.provenance import (
    AbstractProvidesLocalProvenanceData)


class GraphProvenanceGatherer(object):
    __slots__ = []

    def __call__(
            self, machine_graph, application_graph=None,
            provenance_data_objects=None):
        """
        :param machine_graph: The machine graph to inspect
        :param application_graph: The optional application graph
        :param provenance_data_objects: Any existing objects to append to
        """

        if provenance_data_objects is not None:
            prov_items = provenance_data_objects
        else:
            prov_items = list()

        progress = ProgressBar(
            machine_graph.n_vertices +
            machine_graph.n_outgoing_edge_partitions,
            "Getting provenance data from machine graph")
        for vertex in progress.over(machine_graph.vertices, False):
            if isinstance(vertex, AbstractProvidesLocalProvenanceData):
                prov_items.extend(vertex.get_local_provenance_data())
        for partition in progress.over(machine_graph.outgoing_edge_partitions):
            for edge in partition.edges:
                if isinstance(edge, AbstractProvidesLocalProvenanceData):
                    prov_items.extend(edge.get_local_provenance_data())

        if application_graph is not None:
            progress = ProgressBar(
                application_graph.n_vertices +
                application_graph.n_outgoing_edge_partitions,
                "Getting provenance data from application graph")
            for vertex in progress.over(application_graph.vertices, False):
                if isinstance(vertex, AbstractProvidesLocalProvenanceData):
                    prov_items.extend(vertex.get_local_provenance_data())
            for partition in progress.over(
                    application_graph.outgoing_edge_partitions):
                for edge in partition.edges:
                    if isinstance(edge, AbstractProvidesLocalProvenanceData):
                        prov_items.extend(edge.get_local_provenance_data())

        return prov_items
