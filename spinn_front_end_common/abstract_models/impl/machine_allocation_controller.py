import logging
import sys
from threading import Thread
from six import add_metaclass
from spinn_utilities.overrides import overrides
from spinn_utilities.abstract_base import AbstractBase, abstractmethod
from spinn_front_end_common.abstract_models import (
    AbstractMachineAllocationController)

logger = logging.getLogger(__name__)


@add_metaclass(AbstractBase)
class MachineAllocationController(AbstractMachineAllocationController):
    __slots__ = [
        # boolean flag for telling this thread when the system has ended
        "_exited"
    ]

    def __init__(self, thread_name):
        thread = Thread(name=thread_name, target=self.__manage_allocation)
        thread.daemon = True
        self._exited = False
        thread.start()

    @overrides(AbstractMachineAllocationController.close)
    def close(self):
        self._exited = True

    @abstractmethod
    def _wait(self):
        """ Wait for some bounded amount of time for a change in the status\
            of the machine allocation.

        :return: Whether the machine is still (believed to be) allocated.
        :rtype: bool
        """

    def _teardown(self):
        """ Perform any extra teardown that the thread requires. Does not\
            need to be overridden if no action is desired."""
        pass

    def __manage_allocation(self):
        machine_still_allocated = True
        while machine_still_allocated and not self._exited:
            machine_still_allocated = self._wait()
        self._teardown()
        if not self._exited:
            logger.error(
                "The allocated machine has been released before the end of"
                " the script; this script will now exit")
            sys.exit(1)
