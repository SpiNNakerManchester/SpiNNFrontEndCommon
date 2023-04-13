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
from typing import Dict, Tuple
from spinn_utilities.config_holder import get_config_str_list, get_config_bool
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spalloc_client import Job
from spalloc_client.states import JobState
from spinn_utilities.abstract_context_manager import AbstractContextManager
from spinn_utilities.config_holder import get_config_int, get_config_str
from spinn_machine import Machine
from spinnman.constants import SCP_SCAMP_PORT
from spinnman.spalloc import (
    is_server_address, SpallocClient, SpallocJob, SpallocState)
from spinn_front_end_common.abstract_models import (
    AbstractMachineAllocationController)
from spinn_front_end_common.abstract_models.impl import (
    MachineAllocationController)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance import ProvenanceWriter
from spinn_front_end_common.utilities.utility_calls import parse_old_spalloc

logger = FormatAdapter(logging.getLogger(__name__))
_MACHINE_VERSION = 5  # Spalloc only ever works with v5 boards

#: The number of chips per board to use in calculations to ensure that
#: the number of boards allocated is enough.  This is 2 less than the maximum
#: as there are a few boards with 2 down chips in the big machine.
CALC_CHIPS_PER_BOARD = Machine.MAX_CHIPS_PER_48_BOARD - 2


class SpallocJobController(MachineAllocationController):
    __slots__ = (
        # the spalloc job object
        "_job",
        # the current job's old state
        "_state",
        "__client",
        "__closer",
        "__use_proxy"
    )

    def __init__(
            self, client: SpallocClient, job: SpallocJob,
            task: AbstractContextManager, use_proxy: bool):
        """
        :param ~spinnman.spalloc.SpallocClient client:
        :param ~spinnman.spalloc.SpallocJob job:
        :param task:
        :type task:
            ~spinn_utilities.abstract_context_manager.AbstractContextManager
        :param bool use_proxy:
        """
        if job is None:
            raise TypeError("must have a real job")
        self.__client = client
        self.__closer = task
        self._job = job
        self._state = job.get_state()
        self.__use_proxy = use_proxy
        super().__init__("SpallocJobController")

    @overrides(AbstractMachineAllocationController.extend_allocation)
    def extend_allocation(self, new_total_run_time):
        # Does Nothing in this allocator - machines are held until exit
        pass

    @overrides(AbstractMachineAllocationController.close)
    def close(self):
        super().close()
        self.__closer.close()
        self._job.destroy()
        self.__client.close()

    @overrides(AbstractMachineAllocationController.where_is_machine)
    def where_is_machine(self, chip_x, chip_y):
        """
        :param int chip_x:
        :param int chip_y:
        :rtype: tuple(int,int,int)
        """
        return self._job.where_is_machine(x=chip_x, y=chip_y)

    @overrides(MachineAllocationController._wait)
    def _wait(self):
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
    def _teardown(self):
        if not self._exited:
            self.__closer.close()
            self._job.destroy()
            self.__client.close()
        super()._teardown()

    @overrides(AbstractMachineAllocationController.create_transceiver)
    def create_transceiver(self):
        """
        .. note::
            This allocation controller proxies the transceiver's connections
            via Spalloc. This allows it to work even outside the UNIMAN
            firewall.

        """
        if not self.__use_proxy:
            return super(SpallocJobController, self).create_transceiver()
        txrx = self._job.create_transceiver()
        txrx.ensure_board_is_ready()
        return txrx

    @overrides(AbstractMachineAllocationController.open_sdp_connection)
    def open_sdp_connection(self, chip_x, chip_y, udp_port=SCP_SCAMP_PORT):
        """
        .. note::
            This allocation controller proxies connections via Spalloc. This
            allows it to work even outside the UNIMAN firewall.

        """
        return self._job.connect_to_board(chip_x, chip_y, udp_port)

    @overrides(AbstractMachineAllocationController.open_eieio_connection)
    def open_eieio_connection(self, chip_x, chip_y):
        return self._job.open_eieio_connection(chip_x, chip_y, SCP_SCAMP_PORT)

    @overrides(AbstractMachineAllocationController.open_eieio_listener)
    def open_eieio_listener(self):
        return self._job.open_listener_connection()

    @property
    @overrides(AbstractMachineAllocationController.proxying)
    def proxying(self):
        return self.__use_proxy

    @overrides(MachineAllocationController.make_report)
    def make_report(self, filename):
        with open(filename, "w", encoding="utf-8") as report:
            report.write(f"Job: {self._job}")


class _OldSpallocJobController(MachineAllocationController):
    __slots__ = (
        # the spalloc job object
        "_job",
        # the current job's old state
        "_state"
    )

    def __init__(self, job: Job, host: str):
        """
        :param ~spalloc.job.Job job:
        """
        if job is None:
            raise TypeError("must have a real job")
        self._job = job
        self._state = job.state
        super().__init__("SpallocJobController", host)

    @overrides(AbstractMachineAllocationController.extend_allocation)
    def extend_allocation(self, new_total_run_time):
        # Does Nothing in this allocator - machines are held until exit
        pass

    @overrides(AbstractMachineAllocationController.close)
    def close(self):
        super().close()
        self._job.destroy()

    @property
    def power(self) -> bool:
        """
        :rtype: bool
        """
        return self._job.power

    def set_power(self, power: bool):
        """
        :param bool power:
        """
        self._job.set_power(power)
        if power:
            self._job.wait_until_ready()

    @overrides(AbstractMachineAllocationController.where_is_machine)
    def where_is_machine(self, chip_x, chip_y):
        return self._job.where_is_machine(chip_y=chip_y, chip_x=chip_x)

    @overrides(MachineAllocationController._wait)
    def _wait(self):
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
    def _teardown(self):
        if not self._exited:
            self._job.close()
        super()._teardown()


_MACHINE_VERSION = 5


def spalloc_allocator(
        bearer_token: str = None) -> Tuple[
            str, int, None, bool, bool, Dict[Tuple[int, int], str], None,
            MachineAllocationController]:
    """
    Request a machine from a SPALLOC server that will fit the given
    number of chips.

    :param bearer_token: The bearer token to use
    :type bearer_token: str or None
    :return:
        host, board version, BMP details, reset on startup flag,
        auto-detect BMP flag, board address map, allocation controller
    :rtype: tuple(str, int, object, bool, bool, dict(tuple(int,int),str),
        MachineAllocationController)
    """

    spalloc_server = get_config_str("Machine", "spalloc_server")

    # Work out how many boards are needed
    if FecDataView.has_n_boards_required():
        n_boards = FecDataView.get_n_boards_required()
    else:
        n_chips = FecDataView.get_n_chips_needed()
        n_boards_float = float(n_chips) / CALC_CHIPS_PER_BOARD
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
            spalloc_server, n_boards, bearer_token)
    else:
        host, connections, mac = _allocate_job_old(spalloc_server, n_boards)
    return (host, _MACHINE_VERSION, None, False, False, connections, mac)


def _allocate_job_new(
        spalloc_server: str, n_boards: int,
        bearer_token: str = None) -> Tuple[
            str, Dict[Tuple[int, int], str], MachineAllocationController]:
    """
    Request a machine from an new-style spalloc server that will fit the
    given number of boards.

    :param str spalloc_server:
        The server from which the machine should be requested
    :param int n_boards: The number of boards required
    :param bearer_token: The bearer token to use
    :type bearer_token: str or None
    :rtype: tuple(str, dict(tuple(int,int),str), MachineAllocationController)
    """
    logger.info(f"Requesting job with {n_boards} boards")
    with ExitStack() as stack:
        spalloc_machine = get_config_str("Machine", "spalloc_machine")
        use_proxy = get_config_bool("Machine", "spalloc_use_proxy")
        client = SpallocClient(spalloc_server, bearer_token=bearer_token)
        stack.enter_context(client)
        job = client.create_job(n_boards, spalloc_machine)
        stack.enter_context(job)
        task = job.launch_keepalive_task()
        stack.enter_context(task)
        job.wait_until_ready()
        connections = job.get_connections()
        ProvenanceWriter().insert_board_provenance(connections)
        root = connections.get((0, 0), None)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "boards: {}",
                str(connections).replace("{", "[").replace("}", "]"))
        allocation_controller = SpallocJobController(
            client, job, task, use_proxy)
        # Success! We don't want to close the client, job or task now;
        # the allocation controller now owns them.
        stack.pop_all()
        return (root, connections, allocation_controller)


def _allocate_job_old(spalloc_server: str, n_boards: int) -> Tuple[
        str, Dict[Tuple[int, int], str], MachineAllocationController]:
    """
    Request a machine from an old-style spalloc server that will fit the
    requested number of boards.

    :param str spalloc_server:
        The server from which the machine should be requested
    :param int n_boards: The number of boards required
    :rtype: tuple(str, dict(tuple(int,int),str), MachineAllocationController)
    """
    host, port, user = parse_old_spalloc(
        spalloc_server, get_config_int("Machine", "spalloc_port"),
        get_config_str("Machine", "spalloc_user"))
    spalloc_kwargs = {
        'hostname': host,
        'port': port,
        'owner': user
    }
    spalloc_machine = get_config_str("Machine", "spalloc_machine")

    if spalloc_machine is not None:
        spalloc_kwargs['machine'] = spalloc_machine

    job, hostname, scamp_connection_data = _launch_checked_job_old(
        n_boards, spalloc_kwargs)
    machine_allocation_controller = _OldSpallocJobController(job, hostname)
    return (hostname, scamp_connection_data, machine_allocation_controller)


def _launch_checked_job_old(n_boards: int, spalloc_kwargs: dict) -> Tuple[
        Job, str, Dict[Tuple[int, int], str]]:
    """
    :rtype: tuple(~.Job, str, dict(tuple(int,int),str))
    """
    logger.info(f"Requesting job with {n_boards} boards")
    avoid_boards = get_config_str_list("Machine", "spalloc_avoid_boards")
    avoid_jobs = []
    try:
        while True:
            job = Job(n_boards, **spalloc_kwargs)
            try:
                job.wait_until_ready()
                # get param from jobs before starting, so that hanging doesn't
                # occur
                hostname = job.hostname
            except Exception as ex:
                job.destroy(str(ex))
                raise
            connections = job.connections
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
    return job, hostname, connections
