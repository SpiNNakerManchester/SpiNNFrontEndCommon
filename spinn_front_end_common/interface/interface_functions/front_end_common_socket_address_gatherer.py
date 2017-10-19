from spinn_front_end_common.abstract_models.\
    abstract_provides_socket_addresses import \
    AbstractProvidesSocketAddresses
from spinn_machine.utilities.progress_bar import ProgressBar


class FrontEndCommonSocketAddressGatherer(object):
    """
    goes around the vertices and locates socket addresses
    """

    def __call__(self, partitionable_graph, socket_addresses):
        progress_bar = ProgressBar(
            len(list(partitionable_graph.vertices)),
            "Discovering the graph's requested socket addresses's")

        # create list if required
        if socket_addresses is None:
            socket_addresses = set()

        # loop around all vertices looking for socket addresses
        for vertex in partitionable_graph.vertices:
            if isinstance(vertex, AbstractProvidesSocketAddresses):
                vertex_socket_addresses = vertex.get_socket_addresses
                socket_addresses.add(vertex_socket_addresses)
            progress_bar.update()
        progress_bar.end()

        return {"socket_addresses": socket_addresses}
