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

import math
from spinn_utilities.overrides import overrides
from spalloc import Job
from spalloc.states import JobState
from spinn_utilities.config_holder import get_config_int, get_config_str
from spinn_front_end_common.abstract_models import (
    AbstractMachineAllocationController)
from spinn_front_end_common.abstract_models.impl import (
    MachineAllocationController)
from spinn_front_end_common.utilities.spalloc import (
    SpallocClient, SpallocJob, SpallocState)


class _NewSpallocJobController(MachineAllocationController):
    __slots__ = [
        # the spalloc job object
        "_job",
        # the current job's old state
        "_state",
        "__client",
        "__closer"
    ]

    def __init__(self, client, job, closer):
        """
        :param SpallocClient client:
        :param SpallocJob job:
        :param closer:
        """
        if job is None:
            raise Exception("must have a real job")
        self.__client = client
        self.__closer = closer
        self._job: SpallocJob = job
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


class SpallocAllocator(object):
    """ Request a machine from a SPALLOC server that will fit the given\
        number of chips.
    """

    # Use a worst case calculation
    _N_CHIPS_PER_BOARD = 48
    _MACHINE_VERSION = 5

    def __call__(
            self, spalloc_server, n_chips=None, n_boards=None):
        """
        :param str spalloc_server:
            The server from which the machine should be requested
        :param n_chips: The number of chips required.
            IGNORED if n_boards is not None
        :type n_chips: int or None
        :param int n_boards: The number of boards required
        :type n_boards: int or None
        :rtype: tuple(str, int, None, bool, bool, None, None,
            MachineAllocationController)
        """
        # pylint: disable=too-many-arguments

        # Work out how many boards are needed
        if n_boards is None:
            n_boards = float(n_chips) / self._N_CHIPS_PER_BOARD
            # If the number of boards rounded up is less than 10% of a board
            # bigger than the actual number of boards,
            # add another board just in case.
            if math.ceil(n_boards) - n_boards < 0.1:
                n_boards += 1
            n_boards = int(math.ceil(n_boards))

        if SpallocClient.is_server_address(spalloc_server):
            return self.allocate_job_new(spalloc_server, n_boards)
        else:
            return self.allocate_job_old(spalloc_server, n_boards)

    def allocate_job_new(self, spalloc_server, n_boards):
        """
        Request a machine from an old-style spalloc server that will fit the
        given number of boards.

        :param str spalloc_server:
            The server from which the machine should be requested
        :param int n_boards: The number of boards required
        :rtype: tuple(str, int, None, bool, bool, None, None,
            MachineAllocationController)
        """

        spalloc_machine = get_config_str("Machine", "spalloc_machine")
        client = SpallocClient(spalloc_server)
        job = client.create_job(n_boards, spalloc_machine)
        closer_for_keepalive_task = client.launch_keepalive_task(job)
        try:
            job.wait_until_ready()
            root = job.get_root_host()
            machine_allocation_controller = _NewSpallocJobController(
                client, job, closer_for_keepalive_task)
            return (
                root, self._MACHINE_VERSION, None, False,
                False, None, None, machine_allocation_controller
            )
        except Exception:
            closer_for_keepalive_task.close()
            client.close()
            raise

    def allocate_job_old(self, spalloc_server, n_boards):
        """
        Request a machine from an old-style spalloc server that will fit the
        given number of boards.

        :param str spalloc_server:
            The server from which the machine should be requested
        :param int n_boards: The number of boards required
        :rtype: tuple(str, int, None, bool, bool, None, None,
            MachineAllocationController)
        """

        spalloc_kw_args = {
            'hostname': spalloc_server,
            'owner': get_config_str("Machine", "spalloc_user")
        }
        spalloc_port = get_config_int("Machine", "spalloc_port")
        if spalloc_port is not None:
            spalloc_kw_args['port'] = spalloc_port
        spalloc_machine = get_config_str("Machine", "spalloc_machine")
        if spalloc_machine is not None:
            spalloc_kw_args['machine'] = spalloc_machine

        job, hostname = self._launch_job(n_boards, spalloc_kw_args)
        machine_allocation_controller = _OldSpallocJobController(job)

        return (
            hostname, self._MACHINE_VERSION, None, False,
            False, None, None, machine_allocation_controller
        )

    def _launch_job(self, n_boards, spalloc_kw_args):
        """
        :param int n_boards:
        :param dict(str, str or int) spalloc_kw_args:
        :rtype: tuple(~.Job, str)
        """
        job = Job(n_boards, **spalloc_kw_args)
        try:
            job.wait_until_ready()
            # get param from jobs before starting, so that hanging doesn't
            # occur
            return job, job.hostname
        except Exception:
            job.destroy()
            raise
