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
from spinn_utilities.config_holder import get_config_str_list
from spinn_utilities.overrides import overrides
from spalloc import Job
from spalloc.states import JobState
from spinn_machine import Machine
from spinn_utilities.config_holder import get_config_int, get_config_str
from spinn_front_end_common.abstract_models import (
    AbstractMachineAllocationController)
from spinn_front_end_common.abstract_models.impl import (
    MachineAllocationController)
from spinn_front_end_common.interface.provenance import ProvenanceWriter
from spinn_utilities.log import FormatAdapter

logger = FormatAdapter(logging.getLogger(__name__))


class _SpallocJobController(MachineAllocationController):
    __slots__ = [
        # the spalloc job object
        "_job",
        # the current job's old state
        "_state"
    ]

    def __init__(self, job):
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
    def power(self):
        """
        :rtype: bool
        """
        return self._job.power

    def set_power(self, power):
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


_MACHINE_VERSION = 5


def spalloc_allocator(n_chips=None, n_boards=None):
    """ Request a machine from a SPALLOC server that will fit the given\
        number of chips.

    :param n_chips: The number of chips required.
        IGNORED if n_boards is not None
    :type n_chips: int or None
    :param int n_boards: The number of boards required
    :type n_boards: int or None
    :rtype: tuple(str, int, None, bool, bool, None, None,
        MachineAllocationController)
    """

    # Work out how many boards are needed
    if n_boards is None:
        n_boards_float = float(n_chips) / Machine.MAX_CHIPS_PER_48_BOARD
        logger.info("{:.2f} Boards Required for {} chips",
                    n_boards_float, n_chips)
        # If the number of boards rounded up is less than 50% of a board
        # bigger than the actual number of boards,
        # add another board just in case.
        n_boards = int(math.ceil(n_boards_float))
        if n_boards - n_boards_float < 0.5:
            n_boards += 1
    logger.info("Requesting {} boards", n_boards)

    spalloc_kw_args = {
        'hostname': get_config_str("Machine", "spalloc_server"),
        'owner': get_config_str("Machine", "spalloc_user")
    }
    spalloc_port = get_config_int("Machine", "spalloc_port")
    if spalloc_port is not None:
        spalloc_kw_args['port'] = spalloc_port
    spalloc_machine = get_config_str("Machine", "spalloc_machine")

    if spalloc_machine is not None:
        spalloc_kw_args['machine'] = spalloc_machine

    job, hostname, scamp_connection_data = _launch_checked_job(
        n_boards, spalloc_kw_args)
    machine_allocation_controller = _SpallocJobController(job)

    return (
        hostname, _MACHINE_VERSION, None, False,
        False, scamp_connection_data, machine_allocation_controller
    )


def _launch_checked_job(n_boards, spalloc_kw_args):
    logger.info(f"Requesting job with {n_boards} boards")
    avoid_boards = get_config_str_list("Machine", "spalloc_avoid_boards")
    avoid_jobs = []
    job, hostname = _launch_job(n_boards, spalloc_kw_args)
    while True:
        connections = job.connections
        info = str(connections).replace("{", "[").replace("}", "]")
        logger.info("boards: " + info)
        ProvenanceWriter().insert_board_provenance(connections)
        if hostname in avoid_boards:
            avoid_jobs.append(job)
            logger.warning(
                f"Asking for new job as {hostname} "
                f"as in the spalloc_avoid_boards list")
            job, hostname = _launch_job(n_boards, spalloc_kw_args)
        else:
            break
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


def _launch_job(n_boards, spalloc_kw_args):
    """
    :param int n_boards:
    :param dict(str, str or int) spalloc_kw_args:
    :rtype: tuple(~.Job, str)
    """
    job = None
    try:
        job = Job(n_boards, **spalloc_kw_args)
        job.wait_until_ready()
        # get param from jobs before starting, so that hanging doesn't
        # occur
        return job, job.hostname
    except Exception as ex:
        if job:
            job.destroy(str(ex))
        raise
