import math
import logging
import sys
from threading import Thread

from spalloc import Job
from spalloc.states import JobState

from spinn_front_end_common.abstract_models\
    .abstract_machine_allocation_controller \
    import AbstractMachineAllocationController


logger = logging.getLogger(__name__)


class _SpallocJobController(Thread, AbstractMachineAllocationController):

    def __init__(self, job):
        Thread.__init__(self, name="SpallocJobController")
        self.daemon = True
        self._job = job
        self._exited = False

    def extend_allocation(self, new_total_run_time):

        # Does Nothing in this allocator - machines are held until exit
        pass

    def close(self):
        self._exited = True
        self._job.destroy()

    def run(self):
        state = self._job.state
        while state != JobState.destroyed and not self._exited:

            try:
                if self._job is not None:
                    state = self._job.wait_for_state_change(state)
            except TypeError:
                pass

        self._job.close()

        if not self._exited:
            logger.error(
                "The allocated machine has been released before the end of"
                " the script - this script will now exit")
            sys.exit(1)


class FrontEndCommonSpallocAllocator(object):
    """ Request a machine from a SPALLOC server that will fit the given\
        partitioned graph
    """

    # Use a worst case calculation
    _N_CHIPS_PER_BOARD = 48.0
    _MACHINE_VERSION = 5

    def __call__(
            self, spalloc_server, spalloc_user, n_chips, spalloc_port=None):
        """

        :param spalloc_server: The server from which the machine should be\
                    requested
        :param spalloc_port: The port of the SPALLOC server
        :param spalloc_user: The user to allocate the machine to
        :param n_chips: The number of chips required
        """

        # Work out how many boards are needed
        n_boards = float(n_chips) / self._N_CHIPS_PER_BOARD

        # If the number of boards rounded up is less than 10% bigger than the\
        # actual number of boards, add another board just in case
        if math.ceil(n_boards) - n_boards < 0.1:
            n_boards += 1
        n_boards = int(math.ceil(n_boards))

        job = None
        if spalloc_port is None:
            job = Job(n_boards, hostname=spalloc_server, owner=spalloc_user)
        else:
            job = Job(
                n_boards, hostname=spalloc_server, port=spalloc_port,
                owner=spalloc_user)

        try:
            job.wait_until_ready()
        except:
            job.destroy()
            ex_type, ex_value, ex_traceback = sys.exc_info()
            raise ex_type, ex_value, ex_traceback

        # get param from jobs before starting, so that hanging doesn't occur
        width = job.width
        height = job.height
        hostname = job.hostname

        machine_allocation_controller = _SpallocJobController(job)
        machine_allocation_controller.start()

        return {
            "machine_name": hostname,
            "machine_version": self._MACHINE_VERSION,
            "machine_width": width,
            "machine_height": height,
            "machine_n_boards": None,
            "machine_down_chips": None,
            "machine_down_cores": None,
            "machine_bmp_details": None,
            "reset_machine_on_start_up": False,
            "auto_detect_bmp": False,
            "scamp_connection_data": None,
            "boot_port_number": None,
            "max_sdram_size": None,
            "machine_allocation_controller": machine_allocation_controller
        }
