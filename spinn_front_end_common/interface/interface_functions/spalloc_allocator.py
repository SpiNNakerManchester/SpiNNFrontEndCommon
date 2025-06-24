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

from contextlib import ExitStack
import logging
import math
from typing import ContextManager, Dict, Tuple, Optional, Union, cast

from spinn_utilities.config_holder import (
    get_config_bool, get_config_str_or_none, get_config_str_list,
    get_report_path)
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spinn_utilities.typing.coords import XY
from spinn_utilities.config_holder import get_config_int, get_config_str

from spalloc_client import Job
from spalloc_client.states import JobState

from spinnman.connections.udp_packet_connections import (
    SCAMPConnection, EIEIOConnection)
from spinnman.constants import SCP_SCAMP_PORT
from spinnman.spalloc import (
    is_server_address, SpallocClient, SpallocJob, SpallocState)
from spinnman.transceiver import Transceiver

from spinn_front_end_common.abstract_models.impl import (
    MachineAllocationController)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance import ProvenanceWriter
from spinn_front_end_common.utilities.utility_calls import parse_old_spalloc

logger = FormatAdapter(logging.getLogger(__name__))
_MACHINE_VERSION = 5  # Spalloc only ever works with v5 boards


class SpallocJobController(MachineAllocationController):
    """
    A class to Create and support Transceivers specific for Spalloc.
    """

    __slots__ = (
        # the spalloc job object
        "_job",
        # the current job's old state
        "_state",
        "__client",
        "__use_proxy"
    )

    def __init__(
            self, client: SpallocClient, job: SpallocJob, use_proxy: bool):
        if job is None:
            raise TypeError("must have a real job")
        self.__client = client
        self._job = job
        self._state = job.get_state()
        self.__use_proxy = use_proxy
        super().__init__("SpallocJobController")

    @property
    def job(self) -> SpallocJob:
        """
        The job value passed into the init.

        :rtype: SpallocJob
        """
        return self._job

    @overrides(MachineAllocationController.extend_allocation)
    def extend_allocation(self, new_total_run_time: float) -> None:
        # Does Nothing in this allocator - machines are held until exit
        pass

    def __stop(self) -> None:
        self._job.destroy()
        self.__client.close()

    @overrides(MachineAllocationController.close)
    def close(self) -> None:
        super().close()
        self.__stop()

    @overrides(MachineAllocationController.where_is_machine)
    def where_is_machine(
            self, chip_x: int, chip_y: int) -> Tuple[int, int, int]:
        result = self._job.where_is_machine(x=chip_x, y=chip_y)
        if result is None:
            raise ValueError("coordinates lie outside machine")
        return result

    @overrides(MachineAllocationController._wait)
    def _wait(self) -> bool:
        try:
            if self._state != SpallocState.DESTROYED:
                self._state = self._job.wait_for_state_change(self._state)
        except TypeError:
            pass
        except Exception as e:  # pylint: disable=broad-except
            if not self._exited:
                raise e
        return self._state != SpallocState.DESTROYED

    @overrides(MachineAllocationController._teardown)
    def _teardown(self) -> None:
        if not self._exited:
            self.__stop()
        super()._teardown()

    @overrides(MachineAllocationController.create_transceiver,
               extend_doc=True)
    def create_transceiver(self) -> Transceiver:
        """
        .. note::
            This allocation controller proxies the transceiver's connections
            via Spalloc. This allows it to work even outside the UNIMAN
            firewall.
        """
        if not self.__use_proxy:
            return super().create_transceiver()
        txrx = self._job.create_transceiver()
        return txrx

    @overrides(MachineAllocationController.can_create_transceiver)
    def can_create_transceiver(self) -> bool:
        if not self.__use_proxy:
            return super().can_create_transceiver()
        return True

    @overrides(MachineAllocationController.open_sdp_connection,
               extend_doc=True)
    def open_sdp_connection(
            self, chip_x: int, chip_y: int,
            udp_port: int = SCP_SCAMP_PORT) -> Optional[SCAMPConnection]:
        """
        .. note::
            This allocation controller proxies connections via Spalloc. This
            allows it to work even outside the UNIMAN firewall.
        """
        if not self.__use_proxy:
            return super().open_sdp_connection(chip_x, chip_y, udp_port)
        return self._job.connect_to_board(chip_x, chip_y, udp_port)

    @overrides(MachineAllocationController.open_eieio_connection,
               extend_doc=True)
    def open_eieio_connection(
            self, chip_x: int, chip_y: int) -> Optional[EIEIOConnection]:
        """
        .. note::
            This allocation controller proxies connections via Spalloc. This
            allows it to work even outside the UNIMAN firewall.
        """
        if not self.__use_proxy:
            return super().open_eieio_connection(chip_x, chip_y)
        return self._job.open_eieio_connection(chip_x, chip_y)

    @overrides(MachineAllocationController.open_eieio_listener,
               extend_doc=True)
    def open_eieio_listener(self) -> EIEIOConnection:
        """
        .. note::
            This allocation controller proxies connections via Spalloc. This
            allows it to work even outside the UNIMAN firewall.
        """
        if not self.__use_proxy:
            return super().open_eieio_listener()
        return self._job.open_eieio_listener_connection()

    @property
    @overrides(MachineAllocationController.proxying)
    def proxying(self) -> bool:
        return self.__use_proxy

    @overrides(MachineAllocationController.add_report)
    def add_report(self) -> None:
        # as controlled by write_board_chip_report just append there
        filename = get_report_path("path_board_chip_report")
        with open(filename, "a", encoding="utf-8") as report:
            report.write(f"\n\nJob: {self._job}")


class _OldSpallocJobController(MachineAllocationController):
    __slots__ = (
        # the spalloc job object
        "_job",
        # the current job's old state
        "_state"
    )

    def __init__(self, job: Job, host: str):
        if job is None:
            raise TypeError("must have a real job")
        self._job = job
        self._state = job.state
        super().__init__("SpallocJobController", host)

    @overrides(MachineAllocationController.extend_allocation)
    def extend_allocation(self, new_total_run_time: float) -> None:
        # Does Nothing in this allocator - machines are held until exit
        pass

    @overrides(MachineAllocationController.close)
    def close(self) -> None:
        super().close()
        self._job.destroy()

    @property
    def power(self) -> bool:
        """
        The Power of the job
        """
        return self._job.power

    def set_power(self, power: bool) -> None:
        """
        Sets power on the job
        """
        self._job.set_power(power)
        if power:
            self._job.wait_until_ready()

    @overrides(MachineAllocationController.where_is_machine)
    def where_is_machine(
            self, chip_x: int, chip_y: int) -> Tuple[int, int, int]:
        return self._job.where_is_machine(chip_y=chip_y, chip_x=chip_x)

    @overrides(MachineAllocationController._wait)
    def _wait(self) -> bool:
        try:
            if self._state != JobState.destroyed:
                self._state = self._job.wait_for_state_change(self._state)
        except TypeError:
            pass
        except Exception as e:  # pylint: disable=broad-except
            if not self._exited:
                raise e
        return self._state != JobState.destroyed

    @overrides(MachineAllocationController._teardown)
    def _teardown(self) -> None:
        if not self._exited:
            self._job.close()
        super()._teardown()


_MACHINE_VERSION = 5


def spalloc_allocator(
        bearer_token: Optional[str] = None, group: Optional[str] = None,
        collab: Optional[str] = None, nmpi_job: Union[int, str, None] = None,
        nmpi_user: Optional[str] = None) -> Tuple[
            str, int, None, bool, bool, Dict[XY, str],
            MachineAllocationController]:
    """
    Request a machine from a SPALLOC server that will fit the given
    number of chips.

    :param bearer_token: The bearer token to use
    :param group: The group to associate with or None for no group
    :param collab: The collab to associate with or None for no collab
    :param nmpi_job: The NMPI Job to associate with or None for no job
    :param nmpi_user: The NMPI username to associate with or None for no user
    :return:
        host, board version, BMP details, reset on startup flag,
        auto-detect BMP flag, board address map, allocation controller
    """
    spalloc_server = get_config_str("Machine", "spalloc_server")

    # Work out how many boards are needed
    if FecDataView.has_n_boards_required():
        n_boards = FecDataView.get_n_boards_required()
    else:
        n_chips = FecDataView.get_n_chips_needed()
        # reduce max chips by 2 in case you get a bad board(s)
        chips_div = FecDataView.get_machine_version().n_chips_per_board - 2
        n_boards_float = float(n_chips) / chips_div
        logger.info("{:.2f} Boards Required for {} chips",
                    n_boards_float, n_chips)
        # If the number of boards rounded up is less than 50% of a board
        # bigger than the actual number of boards,
        # add another board just in case.
        n_boards = int(math.ceil(n_boards_float))
        if n_boards - n_boards_float < 0.5:
            n_boards += 1

    if is_server_address(spalloc_server):
        host, connections, mac = _allocate_job_new(
            spalloc_server, n_boards, bearer_token, group, collab,
            int(nmpi_job) if nmpi_job is not None else None,
            nmpi_user)
    else:
        host, connections, mac = _allocate_job_old(spalloc_server, n_boards)
    return (host, _MACHINE_VERSION, None, False, False, connections, mac)


def _allocate_job_new(
        spalloc_server: str, n_boards: int,
        bearer_token: Optional[str] = None, group: Optional[str] = None,
        collab: Optional[str] = None, nmpi_job: Optional[int] = None,
        nmpi_user: Optional[str] = None) -> Tuple[
            str, Dict[XY, str], MachineAllocationController]:
    """
    Request a machine from an new-style spalloc server that will fit the
    given number of boards.

    :param spalloc_server:
        The server from which the machine should be requested
    :param n_boards: The number of boards required
    :param bearer_token: The bearer token to use
    :param group: The group to associate with or None for no group
    :param collab: The collab to associate with or None for no collab
    :param nmpi_job: The NMPI Job to associate with or None for no job
    :param nmpi_user: The NMPI username to associate with or None for no user
    """
    logger.info(f"Requesting job with {n_boards} boards")
    with ExitStack() as stack:
        spalloc_machine = get_config_str_or_none("Machine", "spalloc_machine")
        use_proxy = get_config_bool("Machine", "spalloc_use_proxy")
        client = SpallocClient(
            spalloc_server, bearer_token=bearer_token, group=group,
            collab=collab, nmpi_job=nmpi_job, nmpi_user=nmpi_user)
        stack.enter_context(cast(ContextManager[SpallocClient], client))
        job = client.create_job(n_boards, spalloc_machine)
        stack.enter_context(job)
        job.wait_until_ready()
        connections = job.get_connections()
        with ProvenanceWriter() as db:
            db.insert_board_provenance(connections)
        root = connections.get((0, 0), None)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "boards: {}",
                str(connections).replace("{", "[").replace("}", "]"))
        allocation_controller = SpallocJobController(
            client, job, use_proxy or False)
        # Success! We don't want to close the client, job or task now;
        # the allocation controller now owns them.
        stack.pop_all()
    assert root is not None, "no root of ready board"
    return (root, connections, allocation_controller)


def _allocate_job_old(spalloc_server: str, n_boards: int) -> Tuple[
        str, Dict[XY, str], MachineAllocationController]:
    """
    Request a machine from an old-style spalloc server that will fit the
    requested number of boards.

    :param spalloc_server:
        The server from which the machine should be requested
    :param n_boards: The number of boards required
    """
    host, port, owner = parse_old_spalloc(
        spalloc_server, get_config_int("Machine", "spalloc_port"),
        get_config_str("Machine", "spalloc_user"))
    machine = get_config_str_or_none("Machine", "spalloc_machine")

    job, hostname, scamp_connection_data = _launch_checked_job_old(
        n_boards, host, port, owner, machine)
    machine_allocation_controller = _OldSpallocJobController(job, hostname)
    return (hostname, scamp_connection_data, machine_allocation_controller)


def _launch_checked_job_old(
        n_boards: int, host: str, port: int, owner: str,
        machine: Optional[str]) -> Tuple[Job, str, Dict[XY, str]]:
    logger.info(f"Requesting job with {n_boards} boards")
    avoid_boards = get_config_str_list("Machine", "spalloc_avoid_boards")
    avoid_jobs = []
    try:
        while True:
            job = Job(n_boards, hostname=host, port=port, owner=owner,
                      machine=machine)
            try:
                job.wait_until_ready()
                # get param from jobs before starting, so that hanging doesn't
                # occur
                hostname = job.hostname
            except Exception as ex:
                job.destroy(str(ex))
                raise
            connections = job.connections
            if len(connections) < n_boards:
                logger.warning(
                    "boards: {}",
                    str(connections).replace("{", "[").replace("}", "]"))
                raise ValueError("Not enough connections detected")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("boards: {}",
                             str(connections).replace("{", "[").replace(
                                 "}", "]"))
            with ProvenanceWriter() as db:
                db.insert_board_provenance(connections)
            if hostname not in avoid_boards:
                break
            avoid_jobs.append(job)
            logger.warning(
                f"Asking for new job as {hostname} "
                f"as in the spalloc_avoid_boards list")
    finally:
        if avoid_boards:
            for key in list(connections.keys()):
                if connections[key] in avoid_boards:
                    logger.warning(
                        f"Removing connection info for {connections[key]} "
                        f"as in the spalloc avoid_boards list")
                    del connections[key]
        for avoid_job in avoid_jobs:
            avoid_job.destroy("Asked to avoid by cfg")
    assert hostname is not None
    return job, hostname, connections
