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
from typing import Dict, Tuple, Optional

from spinn_utilities.config_holder import (
    get_config_str_or_none, get_config_str_list)
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spinn_utilities.typing.coords import XY
from spinn_utilities.config_holder import get_config_int, get_config_str

from spalloc_client import Job
from spalloc_client.states import JobState

from spinnman.spalloc import MachineAllocationController
from spinnman.spalloc.spalloc_client import get_n_boards

from spinn_front_end_common.interface.provenance import ProvenanceWriter
from spinn_front_end_common.utilities.utility_calls import parse_old_spalloc

logger = FormatAdapter(logging.getLogger(__name__))


class _OldSpallocJobController(MachineAllocationController):
    __slots__ = (
        # the spalloc job object
        "_job",
        # the current job's old state
        "_state"
    )

    def __init__(self, job: Job):
        """
        :param job: Job Used
        """
        if job is None:
            raise TypeError("must have a real job")
        self._job = job
        self._state = job.state

        super().__init__("SpallocJobController")

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


def spalloc_allocate_job_old() -> Tuple[
        str, Dict[XY, str], MachineAllocationController]:
    """
    Request a machine from an old-style spalloc server that will fit the
    requested number of boards.

    :return:
        host, board address map, allocation controller

    """
    spalloc_server = get_config_str("Machine", "spalloc_server")
    n_boards = get_n_boards()
    host, port, owner = parse_old_spalloc(
        spalloc_server, get_config_int("Machine", "spalloc_port"),
        get_config_str("Machine", "spalloc_user"))
    machine = get_config_str_or_none("Machine", "spalloc_machine")

    job, hostname, scamp_connection_data = _launch_checked_job_old(
        n_boards, host, port, owner, machine)
    machine_allocation_controller = _OldSpallocJobController(job)
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
