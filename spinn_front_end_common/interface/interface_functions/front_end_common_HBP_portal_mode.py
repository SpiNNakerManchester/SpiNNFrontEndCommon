
# spinn-front-end-common imports
from spinn_front_end_common.interface import interface_functions

# general imports
import logging
import math
import os
import sys
from threading import Thread

logger = logging.getLogger(__name__)

EXPECTED_MIN_SIZE = 256

class _ResourceKiller(Thread):

    def __init__(self, graph_name, hbp_portal_state):
        Thread.__init__(
            self, name="resource tracker for graph {}".format(graph_name))
        self._hbp_portal_state = hbp_portal_state
        self.daemon = True

    def run(self):
        """
        entry method for the thread
        """
        try:
            self._hbp_portal_state.wait_till_not_ready()
            logger.error("The System's resources were taken away from it "
                         "before it was finished with")
            sys.exit(1)
        except Exception:
            sys.exit(1)

class FrontEndCommonHBPPortalMode(object):
    """
    FrontEndCommonHBPPortalMode
    """

    def __call__(self, hbp_service_provider, partitioned_graph=None):

        # just partitioned, find machine
        return self._start_with_deducing_machine_size(
            partitioned_graph, hbp_service_provider)

    @staticmethod
    def _start_with_deducing_machine_size(
            partitioned_graph, hbp_service_provider):
        cores = len(partitioned_graph.subvertices)
        number_of_boards = int(math.ceil(float(cores) / float(48 * 15)))

        # get data
        service_provider = hbp_service_provider(number_of_boards)
        service_provider.create()
        service_provider.wait_until_ready()
        results = service_provider.get_machine_info()
        checker_thread = _ResourceKiller(partitioned_graph.label,
                                         service_provider)
        checker_thread.start()

        # define algorithms
        algorithms = list()
        algorithms.append("FrontEndCommonMachineGenerator")
        algorithms.append("MallocBasedChipIDAllocator")

        # define outputs
        required_outputs = list()
        required_outputs.append("MemoryMachine")
        required_outputs.append("MemoryExtendedMachine")

        # xml paths
        xml_paths = list()
        xml_paths.append(os.path.join(
            os.path.dirname(interface_functions.__file__),
            "front_end_common_interface_functions.xml"))

        # inputs
        inputs = list()
        # get results into dict and return
        returned_results = dict()
        for result in results['connections']:
            if result == "(0, 0)":
                returned_results["ip_address"] = results['connections'][result]
        returned_results['hbp_portal_state'] = service_provider
        returned_results['bmp_details'] = None
        returned_results['width'] = results["width"]
        returned_results['height'] = results["height"]
        returned_results['version'] = 5
        return returned_results
