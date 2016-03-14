from spinn_front_end_common.utilities.utility_objs\
    .abstract_machine_allocation_controller \
    import AbstractMachineAllocationController

from threading import Thread
import math
import requests


class _HBPJobController(Thread, AbstractMachineAllocationController):

    def __init__(self, url, job_id):
        Thread.__init__(self)
        self._url = url
        self._job_id = job_id
        self._exited = False

    def extend_allocation(self, new_total_run_time):

        # TODO:
        pass

    def close(self):

        # TODO:
        pass

    def run(self):

        # TODO:
        pass


class FrontEndCommonHBPAllocator(object):
    """ Request a machine from the HBP remote access server that will fit\
        a given partitioned graph
    """

    # Use a worst case calculation
    _N_CORES_PER_CHIP = 15.0

    def __call__(
            self, hbp_server_url, job_id, run_time, partitioned_graph):
        """

        :param hbp_server_url: The URL of the HBP server from which to get\
                    the machine
        :param job_id: The id of the job to request a machine for
        :param run_time: The total run time to request
        :param partitioned_graph: The partitioned graph to allocate for
        """

        # Work out how many boards are needed
        n_cores = len(partitioned_graph.subvertices)
        n_chips = int(math.ceil(float(n_cores) / self._N_CORES_PER_CHIP))

        url = hbp_server_url
        if url.endswith("/"):
            url = url[:-1]

        get_machine_request = requests.get(
            "{}/job/{}/machine".format(url, job_id),
            nChips=n_chips, runTime=run_time)
        machine = get_machine_request.json()

