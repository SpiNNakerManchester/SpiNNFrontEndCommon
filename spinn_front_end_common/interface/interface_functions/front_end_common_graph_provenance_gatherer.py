# pacman imports
from spinn_machine.utilities.progress_bar import ProgressBar

# front end common imports
from spinn_front_end_common.interface.provenance\
    .abstract_provides_local_provenance_data \
    import AbstractProvidesLocalProvenanceData


class FrontEndCommonGraphProvenanceGatherer(object):

    def __call__(
            self, partitioned_graph, partitionable_graph=None,
            provenance_data_objects=None):
        """

        :param partitioned_graph: The partitioned graph to inspect
        :param partitionable_graph: The optional partitionable graph
        :param provenance_data_objects: Any existing objects to append to
        """

        if provenance_data_objects is not None:
            prov_items = provenance_data_objects
        else:
            prov_items = list()

        progress = ProgressBar(
            len(partitioned_graph.subvertices) +
            len(partitioned_graph.subedges),
            "Getting provenance data from partitioned graph")
        for subvertex in partitioned_graph.subvertices:
            if isinstance(subvertex, AbstractProvidesLocalProvenanceData):
                prov_items.extend(subvertex.get_local_provenance_data())
            progress.update()
        for subedge in partitioned_graph.subedges:
            if isinstance(subedge, AbstractProvidesLocalProvenanceData):
                prov_items.extend(subedge.get_local_provenance_data())
            progress.update()
        progress.end()

        if partitionable_graph is not None:
            progress = ProgressBar(
                len(partitionable_graph.vertices) +
                len(partitionable_graph.edges),
                "Getting provenance data from partitionable graph")
            for vertex in partitionable_graph.vertices:
                if isinstance(vertex, AbstractProvidesLocalProvenanceData):
                    prov_items.extend(vertex.get_local_provenance_data())
                progress.update()
            for edge in partitionable_graph.edges:
                if isinstance(edge, AbstractProvidesLocalProvenanceData):
                    prov_items.extend(edge.get_local_provenance_data())
            progress.end()

        return {'prov_items': prov_items}
