from spinn_front_end_common.interface.interface_functions.front_end_common_virtual_machine_generator import \
    FrontEndCommonVirtualMachineGenerator
from spinn_front_end_common.utilities import exceptions

import logging
import math

logger = logging.getLogger(__name__)


class FrontEndCommonHBPPortalMode(object):

    def __call__(self, partitionable_graph=None, starting=True,
                 partitioning_algorithm=None, HBP_portal_state=None,
                 partitioned_graph=None, max_machine_height=None,
                 max_machine_width=None):

        if starting:
            # check that i have a graph
            if partitionable_graph is None and partitioned_graph is None:
                raise exceptions.ConfigurationException(
                    "I'm starting and have not been given a graph. "
                    "Please fix and try again")

            # check that i have vm dimensions
            if max_machine_height is None or max_machine_width is None:
                raise exceptions.ConfigurationException(
                    "I'm starting and have not been given the dimensions of "
                    "the biggest HBP portal machine available. Please fix and "
                    "try again")

            # if ive got both graphs, use partitioned
            if (partitionable_graph is not None and
                    partitioned_graph is not None):
                logger.warn(
                    "FrontEndCommonHBPPortalMode was given both types of graph."
                    " I will use the partitioned graph and ignore the "
                    "partitionable version.")
                return self._start_with_deducing_machine_size(partitioned_graph)

            # if just partitionable do partitioning
            if partitionable_graph is not None and partitioned_graph is None:
                return self._start_with_partitioning(
                    partitionable_graph, partitioning_algorithm,
                    max_machine_height, max_machine_width)

            # just partitioned, find machine
            elif partitionable_graph is None and partitioned_graph is not None:
                return self._start_with_deducing_machine_size(partitioned_graph)
        else:  # running in exit mode

            # check i have the portal state
            if HBP_portal_state is None:
                raise exceptions.ConfigurationException(
                    "If i'm exiting and have not been given a HBP_portal_state"
                    ". Please fix and try again")

            # dealloc machine
            HBP_portal_state.close()

    def _start_with_deducing_machine_size(self, partitioned_graph):
        cores = len(partitioned_graph.subvertices)
        number_of_boards = math.ceil(cores / (48 * 15))




    def _start_with_partitioning(
            self, partitionable_graph, partitioning_algorithm,
            max_machine_height, max_machine_width):

        # get vm
        virtual_machine_builder = FrontEndCommonVirtualMachineGenerator()
        results = virtual_machine_builder(
            max_machine_height, max_machine_width, False, None)
        virtual_machine = results['machine']

        if partitioning_algorithm == "SpreaderPartitioner":
            return self._handle_spreader(
                partitionable_graph, partitioning_algorithm, virtual_machine)
        else:
            return self._handle_normal_partitioners(
                partitionable_graph, partitioning_algorithm, virtual_machine)

    def _handle_spreader(
            self, partitionable_graph, partitioning_algorithm, virtual_machine):
        pass

    def _handle_normal_partitioners(
            self, partitionable_graph, partitioning_algorithm, virtual_machine):
        # run partitioning
        partition_algorithm = partitioning_algorithm()
        results = partition_algorithm(graph=partitionable_graph,
                                      machine=virtual_machine)

        # get partitioning results
        partitioned_graph = results['Partitioned_graph']
        graph_mapper = results['Graph_mapper']

        # get memory machine
        results = self._start_with_deducing_machine_size(partitioned_graph)

        memory_machine = results['MemoryMachine']
        transciever = results['Transciever']
        HBP_portal_state = results['HBP_portal_state']

        return {'partitioned_graph': partitioned_graph,
                'graph_mapper': graph_mapper,
                'memory_machine': memory_machine,
                'txrx': transciever,
                'HBP_portal_state': HBP_portal_state}
