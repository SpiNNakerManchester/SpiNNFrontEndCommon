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
import math
from typing import Dict, Tuple
from spinn_utilities.config_holder import get_config_str_list
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spalloc import Job
from spalloc.states import JobState
from spinn_utilities.abstract_context_manager import AbstractContextManager
from spinn_utilities.config_holder import get_config_int, get_config_str
from spinn_machine import Machine
from spinnman.spalloc import (
    is_server_address, SpallocClient, SpallocJob, SpallocState)
from spinn_front_end_common.abstract_models import (
    AbstractMachineAllocationController)
from spinn_front_end_common.abstract_models.impl import (
    MachineAllocationController)
from spinn_front_end_common.interface.provenance import ProvenanceWriter
from spinn_front_end_common.utilities.spalloc import parse_old_spalloc

logger = FormatAdapter(logging.getLogger(__name__))
_MACHINE_VERSION = 5  # Spalloc only ever works with v5 boards


class _NewSpallocJobController(MachineAllocationController):
    __slots__ = [
        # the spalloc job object
        "_job",
        # the current job's old state
        "_state",
        "__client",
        "__closer"
    ]

    def __init__(
            self, client: SpallocClient, job: SpallocJob,
            task: AbstractContextManager):
        """
        :param SpallocClient client:
        :param SpallocJob job:
        :param AbstractContextManager task:
        """
        if job is None:
            raise Exception("must have a real job")
        self.__client = client
        self.__closer = task
        self._job = job
        self._state = job.get_state()
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
        return self._job.where_is_machine(chip_y=chip_y, chip_x=chip_x)

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
            self._job.close()
            self.__client.close()
        super()._teardown()


class _OldSpallocJobController(MachineAllocationController):
    __slots__ = [
        # the spalloc job object
        "_job",
        # the current job's old state
        "_state"
    ]

    def __init__(self, job: Job):
        """
        :param ~spalloc.job.Job job:
        """
        if job is None:
            raise Exception("must have a real job")
        self._job = job
        self._state = job.state
        super().__init__("SpallocJobController")

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
        """
        :param int chip_x:
        :param int chip_y:
        :rtype: tuple(int,int,int)
        """
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


def spalloc_allocator(
        n_chips: int = None, n_boards: int = None,
        bearer_token: str = None) -> Tuple[
            str, int, None, bool, bool, Dict[Tuple[int, int], str], None,
            MachineAllocationController]:
    """ Request a machine from a SPALLOC server that will fit the given\
        number of chips.

    :param n_chips: The number of chips required.
        IGNORED if n_boards is not None
    :type n_chips: int or None
    :param int n_boards: The number of boards required
    :type n_boards: int or None
    :param bearer_token: The bearer token to use
    :type bearer_token: str or None
    :rtype: tuple(str, int, None, bool, bool, dict(tuple(int,int),str), None,
        MachineAllocationController)
    """

    # Work out how many boards are needed
    spalloc_server = get_config_str("Machine", "spalloc_server")
    if n_boards is None:
        n_boards = float(n_chips) / Machine.MAX_CHIPS_PER_48_BOARD
        # If the number of boards rounded up is less than 10% of a board
        # bigger than the actual number of boards,
        # add another board just in case.
        if math.ceil(n_boards) - n_boards < 0.1:
            n_boards += 1
        n_boards = int(math.ceil(n_boards))
    if is_server_address(spalloc_server):
        host, connections, mac = _allocate_job_new(
            spalloc_server, n_boards, bearer_token)
    else:
        host, connections, mac = _alloc_job_old(spalloc_server, n_boards)
    return (host, _MACHINE_VERSION, None, False, False, connections, None,
            mac)


def _allocate_job_new(
        spalloc_server: str, n_boards: int,
        bearer_token: str = None) -> Tuple[
            str, Dict[Tuple[int, int], str], MachineAllocationController]:
    """
    Request a machine from an old-style spalloc server that will fit the
    given number of boards.

    :param str spalloc_server:
        The server from which the machine should be requested
    :param int n_boards: The number of boards required
    :param bearer_token: The bearer token to use
    :type bearer_token: str or None
    :rtype: tuple(str, dict(tuple(int,int),str), MachineAllocationController)
    """
    logger.info(f"Requesting job with {n_boards} boards")
    spalloc_machine = get_config_str("Machine", "spalloc_machine")
    client = SpallocClient(spalloc_server, bearer_token=bearer_token)
    task = None
    try:
        job = client.create_job(n_boards, spalloc_machine)
        task = job.launch_keepalive_task()
        try:
            job.wait_until_ready()
            connections = job.get_connections()
        except Exception as ex:
            try:
                job.destroy(str(ex))
            except Exception:  # pylint: disable=broad-except
                # Ignore faults in destruction; job will die anyway or even
                # already be dead. Either way, no problem
                pass
            raise
        ProvenanceWriter().insert_board_provenance(connections)
        root = connections.get((0, 0), None)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("boards: {}",
                         str(connections).replace("{", "[").replace("}", "]"))
        allocation_controller = _NewSpallocJobController(client, job, task)
        # Success! We don't want to close the client or task now;
        # the allocation controller now owns them.
        client = None
        task = None
        return (root, connections, allocation_controller)
    finally:
        if task:
            task.close()
        if client:
            client.close()


def _alloc_job_old(spalloc_server: str, n_boards: int) -> Tuple[
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
    machine_allocation_controller = _OldSpallocJobController(job)
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
            ProvenanceWriter().insert_board_provenance(connections)
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
