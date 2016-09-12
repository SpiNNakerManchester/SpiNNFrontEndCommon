from threading import Thread
import requests
import logging
import sys

from spinn_front_end_common.abstract_models\
    .abstract_machine_allocation_controller \
    import AbstractMachineAllocationController

logger = logging.getLogger(__name__)


class _HBPJobController(Thread, AbstractMachineAllocationController):

    __slots__ = [
        # thread flag to allow it to be killed when the main thread dies
        "daemon",

        # the URL to call the HBP system
        "_url",

        # boolean flag for telling this thread when the system has ended
        "_exited"
    ]

    _WAIT_TIME_MS = 10000

    def __init__(self, url):
        Thread.__init__(self, name="HBPJobController")
        self.daemon = True
        self._url = url
        self._exited = False

    def extend_allocation(self, new_total_run_time):
        requests.get(
            "{}/extendLease".format(self._url),
            params={"runTime": new_total_run_time})

    def close(self):
        self._exited = True

    def run(self):
        job_allocated = True
        while job_allocated and not self._exited:
            job_allocated_request = requests.get(
                "{}/checkLease".format(self._url),
                params={"waitTime": self._WAIT_TIME_MS})
            job_allocated = job_allocated_request.json()["allocated"]

        if not self._exited:
            logger.error(
                "The allocated machine has been released before the end of"
                " the script - this script will now exit")
            sys.exit(1)


class FrontEndCommonHBPAllocator(object):
    """ Request a machine from the HBP remote access server that will fit\
        a number of chips
    """

    def __call__(
            self, hbp_server_url, total_run_time, n_chips):
        """

        :param hbp_server_url: The URL of the HBP server from which to get\
                    the machine
        :param total_run_time: The total run time to request
        :param n_chips: The number of chips required
        """

        url = hbp_server_url
        if url.endswith("/"):
            url = url[:-1]

        get_machine_request = requests.get(
            url, params={"nChips": n_chips, "runTime": total_run_time})
        machine = get_machine_request.json()
        machine_allocation_controller = _HBPJobController(url)
        machine_allocation_controller.start()

        bmp_details = None
        if "bmp_details" in machine:
            bmp_details = machine["bmpDetails"]

        return (
            machine["machineName"], int(machine["version"]), None, None,
            bmp_details, False, False, None, None, None,
            machine_allocation_controller
        )
