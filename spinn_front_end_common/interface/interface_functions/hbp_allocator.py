# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import requests
from spinn_utilities.overrides import overrides
from spinn_front_end_common.abstract_models.impl import (
    MachineAllocationController)
from spinn_front_end_common.abstract_models import (
    AbstractMachineAllocationController)
from pacman.exceptions import PacmanConfigurationException


class _HBPJobController(MachineAllocationController):
    __slots__ = [
        # the URLs to call the HBP system
        "_extend_lease_url",
        "_check_lease_url",
        "_release_machine_url",
        "_set_power_url",
        "_where_is_url",
        "_machine_name",
        "_power_on"
    ]

    _WAIT_TIME_MS = 10000

    def __init__(self, url, machine_name):
        self._extend_lease_url = "{}/extendLease".format(url)
        self._check_lease_url = "{}/checkLease".format(url)
        self._release_machine_url = url
        self._set_power_url = "{}/power".format(url)
        self._where_is_url = "{}/chipCoordinates".format(url)
        self._machine_name = machine_name
        self._power_on = True
        # Lower the level of requests to WARNING to avoid extra messages
        logging.getLogger("requests").setLevel(logging.WARNING)
        super(_HBPJobController, self).__init__("HBPJobController")

    @overrides(AbstractMachineAllocationController.extend_allocation)
    def extend_allocation(self, new_total_run_time):
        r = requests.get(self._extend_lease_url, params={
            "runTime": new_total_run_time})
        r.raise_for_status()

    def _check_lease(self, wait_time):
        r = requests.get(self._check_lease_url, params={
            "waitTime": wait_time})
        r.raise_for_status()
        return r.json()

    def _release(self, machine_name):
        r = requests.delete(self._release_machine_url, params={
            "machineName": machine_name})
        r.raise_for_status()

    def _set_power(self, machine_name, power_on):
        r = requests.put(self._set_power_url, params={
            "machineName": machine_name, "on": bool(power_on)})
        r.raise_for_status()

    def _where_is(self, machine_name, chip_x, chip_y):
        r = requests.get(self._where_is_url, params={
            "machineName": machine_name, "chipX": chip_x,
            "chipY": chip_y})
        r.raise_for_status()
        return r.json()

    @overrides(AbstractMachineAllocationController.close)
    def close(self):
        super(_HBPJobController, self).close()
        self._release(self._machine_name)

    @overrides(MachineAllocationController._teardown)
    def _teardown(self):
        self._release(self._machine_name)

    @property
    def power(self):
        return self._power_on

    def set_power(self, power):
        self._set_power(self._machine_name, power)
        self._power_on = power

    def where_is_machine(self, chip_x, chip_y):
        return self._where_is(self._machine_name, chip_x, chip_y)

    @overrides(MachineAllocationController._wait)
    def _wait(self):
        return self._check_lease(self._WAIT_TIME_MS)["allocated"]


class HBPAllocator(object):
    """ Request a machine from the HBP remote access server that will fit\
        a number of chips.
    """

    def __call__(
            self, hbp_server_url, total_run_time, n_chips=None, n_boards=None):
        """

        :param hbp_server_url: \
            The URL of the HBP server from which to get the machine
        :param total_run_time: The total run time to request
        :param n_chips: The number of chips required.
            Only used if n_boards is None
        :param n_boards: The number of boards required
        :raises PacmanConfigurationException:
            If neither n_chips or n_baords provided
        """

        url = hbp_server_url
        if url.endswith("/"):
            url = url[:-1]

        machine = self._get_machine(url, n_chips, n_boards, total_run_time)
        hbp_job_controller = _HBPJobController(url, machine["machineName"])

        bmp_details = None
        if "bmp_details" in machine:
            bmp_details = machine["bmpDetails"]

        return (
            machine["machineName"], int(machine["version"]),
            bmp_details, False, False, None, None,
            hbp_job_controller)

    def _get_machine(self, url, n_chips, n_boards, total_run_time):
        if n_boards:
            get_machine_request = requests.get(
                url, params={"nBoards": n_boards, "runTime": total_run_time})
        elif n_chips:
            get_machine_request = requests.get(
                url, params={"nChips": n_chips, "runTime": total_run_time})
        else:
            raise PacmanConfigurationException(
                "At least one of n_chips or n_boards must be provided")

        get_machine_request.raise_for_status()
        return get_machine_request.json()
