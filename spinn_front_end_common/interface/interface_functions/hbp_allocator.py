# Copyright (c) 2016 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
from typing import Optional, Tuple, cast

import requests

from spinn_utilities.config_holder import get_config_int, get_config_str
from spinn_utilities.overrides import overrides
from spinn_utilities.typing.json import JsonArray, JsonObject

from spinnman.spalloc import MachineAllocationController
from pacman.exceptions import PacmanConfigurationException

from spinn_front_end_common.data import FecDataView


class _HBPJobController(MachineAllocationController):
    __slots__ = (
        # the URLs to call the HBP system
        "_extend_lease_url",
        "_check_lease_url",
        "_release_machine_url",
        "_set_power_url",
        "_where_is_url",
        "_machine_name",
        "_power_on")

    _WAIT_TIME_MS = 10000

    def __init__(self, url: str, machine_name: str):
        """
        :param url:
        :param machine_name:
        """
        self._extend_lease_url = f"{url}/extendLease"
        self._check_lease_url = f"{url}/checkLease"
        self._release_machine_url = url
        self._set_power_url = f"{url}/power"
        self._where_is_url = f"{url}/chipCoordinates"
        self._machine_name = machine_name
        self._power_on = True
        # Lower the level of requests to WARNING to avoid extra messages
        logging.getLogger("requests").setLevel(logging.WARNING)
        super().__init__("HBPJobController")

    @overrides(MachineAllocationController.extend_allocation)
    def extend_allocation(self, new_total_run_time: float) -> None:
        r = requests.get(self._extend_lease_url, params={
            "runTime": str(new_total_run_time)}, timeout=10)
        r.raise_for_status()

    def _check_lease(self, wait_time: int) -> JsonObject:
        r = requests.get(self._check_lease_url, params={
            "waitTime": str(wait_time)}, timeout=10 + wait_time)
        r.raise_for_status()
        return r.json()

    def _release(self, machine_name: str) -> None:
        r = requests.delete(self._release_machine_url, params={
            "machineName": machine_name}, timeout=10)
        r.raise_for_status()

    def _set_power(self, machine_name: str, power_on: bool) -> None:
        r = requests.put(self._set_power_url, params={
            "machineName": machine_name, "on": str(power_on)}, timeout=10)
        r.raise_for_status()

    def _where_is(
            self, machine_name: str, chip_x: int, chip_y: int) -> JsonArray:
        r = requests.get(self._where_is_url, params={
            "machineName": machine_name, "chipX": str(chip_x),
            "chipY": str(chip_y)}, timeout=10)
        r.raise_for_status()
        return r.json()

    @overrides(MachineAllocationController.close)
    def close(self) -> None:
        super().close()
        self._release(self._machine_name)

    @overrides(MachineAllocationController._teardown)
    def _teardown(self) -> None:
        self._release(self._machine_name)

    @property
    def power(self) -> bool:
        """
        The last power state set.
        """
        return self._power_on

    def set_power(self, power: bool) -> None:
        """
        Sets the power to the new state.
        """
        self._set_power(self._machine_name, power)
        self._power_on = power

    @overrides(MachineAllocationController.where_is_machine)
    def where_is_machine(self, chip_x: int, chip_y: int) -> Tuple[
            int, int, int]:
        c, f, b = cast(Tuple[int, int, int],
                       self._where_is(self._machine_name, chip_x, chip_y))
        return (c, f, b)

    @overrides(MachineAllocationController._wait)
    def _wait(self) -> bool:
        return bool(self._check_lease(self._WAIT_TIME_MS)["allocated"])


def hbp_allocator(total_run_time: Optional[float]) -> Tuple[
        str, Optional[str], MachineAllocationController]:
    """
    Request a machine from the HBP remote access server that will fit
    a number of chips.

    :param total_run_time: The total run time to request
    :return: IP address, BMP details (if any), allocation controller
    :raises ~pacman.exceptions.PacmanConfigurationException:
        If neither `n_chips` or `n_boards` provided or if version is incorrect
    """

    url = get_config_str("Machine", "remote_spinnaker_url")
    if url.endswith("/"):
        url = url[:-1]

    machine = _get_machine(url, total_run_time)
    if cast(int, machine["version"]) != get_config_int("Machine", "version"):
        raise PacmanConfigurationException(
            f"Version returned by HBP {machine['version']} == "
            f'version in cfg {get_config_int("Machine", "version")}')
    name = cast(str, machine["machineName"])
    hbp_job_controller = _HBPJobController(url, name)

    return (
        name, cast(Optional[str], machine.get("bmpDetails")),
        hbp_job_controller)


def _get_machine(url: str, total_run_time: Optional[float]) -> JsonObject:
    if FecDataView.has_n_boards_required():
        get_machine_request = requests.get(
            url, params={"nBoards": FecDataView.get_n_boards_required(),
                         "runTime": total_run_time}, timeout=30)
    elif FecDataView.has_n_chips_needed():
        get_machine_request = requests.get(
            url, params={"nChips": FecDataView.get_n_chips_needed(),
                         "runTime": total_run_time}, timeout=30)
    else:
        raise PacmanConfigurationException(
            "At least one of n_chips or n_boards must be provided")

    get_machine_request.raise_for_status()
    return get_machine_request.json()
