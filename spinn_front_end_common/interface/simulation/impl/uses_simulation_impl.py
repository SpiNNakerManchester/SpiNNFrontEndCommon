from spinn_front_end_common.interface.simulation.\
    abstract_uses_simulation import AbstractUsesSimulation
from spinn_front_end_common.utilities import constants

import os
import hashlib


class UsesSimulationImpl(AbstractUsesSimulation):

    def __init__(self, machine_time_step, time_scale_factor):
        AbstractUsesSimulation.__init__(self)
        self._machine_time_step = machine_time_step
        self._time_scale_factor = time_scale_factor

    def data_for_simulation_data(self):
        # Hash application title
        application_name = os.path.splitext(self.get_binary_file_name())[0]

        # Get first 32-bits of the md5 hash of the application name
        application_name_hash = hashlib.md5(application_name).hexdigest()[:8]

        # Write this to the system region (to be picked up by the simulation):
        data = list()
        data.append(int(application_name_hash, 16))
        data.append(self._machine_time_step * self._time_scale_factor)

        # add SDP port number for receiving synchronisations and new run times
        data.append(constants.SDP_PORTS.RUNNING_COMMAND_SDP_PORT.value)

        return data
