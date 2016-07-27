from spinn_front_end_common.utilities import constants
from spinn_front_end_common.abstract_models.\
    abstract_generates_data_specification import \
    AbstractGeneratesDataSpecification
from spinn_front_end_common.abstract_models.\
    abstract_has_associated_binary import \
    AbstractHasAssociatedBinary
from spinn_storage_handlers.file_data_writer import FileDataWriter

from pacman.executor.injection_decorator import \
    supports_injection, inject

import hashlib
import tempfile
import os
import threading

# used to stop file conflicts
_lock_condition = threading.Condition()


@supports_injection
class DataSpecableVertex(
    AbstractGeneratesDataSpecification, AbstractHasAssociatedBinary):

    def __init__(self, machine_time_step, timescale_factor):
        AbstractGeneratesDataSpecification.__init__(self)
        AbstractHasAssociatedBinary.__init__(self)
        self._machine_time_step = machine_time_step
        self._timescale_factor = timescale_factor
        self._no_machine_time_steps = None

    def _write_basic_setup_info(self, spec, region_id):

        # Hash application title
        application_name = os.path.splitext(self.get_binary_file_name())[0]

        # Get first 32-bits of the md5 hash of the application name
        application_name_hash = hashlib.md5(application_name).hexdigest()[:8]

        # Write this to the system region (to be picked up by the simulation):
        spec.switch_write_focus(region=region_id)
        spec.write_value(data=int(application_name_hash, 16))
        spec.write_value(data=self._machine_time_step * self._timescale_factor)

        # add SDP port number for receiving synchronisations and new run times
        spec.write_value(
            data=constants.SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value)

    @inject("MemoryNoMachineTimeSteps")
    def set_no_machine_time_steps(self, new_no_machine_time_steps):
        """

        :param new_no_machine_time_steps:
        :return:
        """
        self._no_machine_time_steps = new_no_machine_time_steps
