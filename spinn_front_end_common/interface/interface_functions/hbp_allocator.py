import logging
import requests
from spinn_utilities.overrides import overrides

from spinn_front_end_common.abstract_models.impl \
    import MachineAllocationController
from spinn_front_end_common.abstract_models \
    import AbstractMachineAllocationController


class _HBPJobController(MachineAllocationController):
    __slots__ = [
        # the URLs to call the HBP system
        "_extend_lease_url",
        "_check_lease_url"
    ]

    _WAIT_TIME_MS = 10000

    def __init__(self, url):
        self._extend_lease_url = "{}/extendLease".format(url)
        self._check_lease_url = "{}/checkLease".format(url)
        # Lower the level of requests to WARNING to avoid extra messages
        logging.getLogger("requests").setLevel(logging.WARNING)
        super(_HBPJobController, self).__init__("HBPJobController")

    @overrides(AbstractMachineAllocationController.extend_allocation)
    def extend_allocation(self, new_total_run_time):
        requests.get(self._extend_lease_url, params={
            "runTime": new_total_run_time})

    def _check_lease(self, wait_time):
        return requests.get(self._check_lease_url, params={
            "waitTime": wait_time}).json()

    @property
    def power(self):
        # TODO NEEDS FIXING
        return True

    def set_power(self, power):
        # TODO NEEDS FIXING
        pass

    def where_is_machine(self, chip_x, chip_y):
        # TODO NEEDS FIXING
        pass

    @overrides(MachineAllocationController._wait)
    def _wait(self):
        return self._check_lease(self._WAIT_TIME_MS)["allocated"]


class HBPAllocator(object):
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

        machine = self._get_machine(url, n_chips, total_run_time)
        hbp_job_controller = _HBPJobController(url)

        bmp_details = None
        if "bmp_details" in machine:
            bmp_details = machine["bmpDetails"]

        return (
            machine["machineName"], int(machine["version"]),
            bmp_details, False, False, None, None,
            hbp_job_controller)

    def _get_machine(self, url, n_chips, total_run_time):
        get_machine_request = requests.get(
            url, params={"nChips": n_chips, "runTime": total_run_time})
        return get_machine_request.json()
