from threading import Thread
import requests
import logging
import sys

from spinn_front_end_common.abstract_models\
    .abstract_machine_allocation_controller \
    import AbstractMachineAllocationController

logger = logging.getLogger(__name__)


class _HBPJobController(Thread, AbstractMachineAllocationController):

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
        a given partitioned graph
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

        return {
            "machine_name": machine["machineName"],
            "machine_version": int(machine["version"]),
            "machine_width": int(machine["width"]),
            "machine_height": int(machine["height"]),
            "machine_n_boards": None,
            "machine_down_chips": None,
            "machine_down_cores": None,
            "machine_bmp_details": bmp_details,
            "reset_machine_on_start_up": False,
            "auto_detect_bmp": False,
            "scamp_connection_data": None,
            "boot_port_number": None,
            "max_sdram_size": None,
            "machine_allocation_controller": machine_allocation_controller
        }
