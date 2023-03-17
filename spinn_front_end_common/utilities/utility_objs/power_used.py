# Copyright (c) 2017 The University of Manchester
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

from collections import defaultdict


class PowerUsed(object):
    """
    Describes the power used by a simulation.
    """

    __slots__ = [
        "__num_chips",
        "__num_cores",
        "__num_fpgas",
        "__num_frames",
        "__exec_time",
        "__mapping_time",
        "__data_gen_time",
        "__loading_time",
        "__saving_time",
        "__chip_energy",
        "__fpga_total_energy",
        "__fpga_exec_energy",
        "__baseline_energy",
        "__packet_energy",
        "__mapping_energy",
        "__data_gen_energy",
        "__loading_energy",
        "__saving_energy",
        "__core_energy",
        "__router_energy"]

    def __init__(self):
        self.__num_chips = 0
        self.__num_cores = 0
        self.__num_fpgas = 0
        self.__num_frames = 0
        self.__exec_time = 0.0
        self.__mapping_time = 0.0
        self.__data_gen_time = 0.0
        self.__loading_time = 0.0
        self.__saving_time = 0.0
        self.__chip_energy = 0.0
        self.__fpga_total_energy = 0.0
        self.__fpga_exec_energy = 0.0
        self.__baseline_energy = 0.0
        self.__packet_energy = 0.0
        self.__mapping_energy = 0.0
        self.__data_gen_energy = 0.0
        self.__loading_energy = 0.0
        self.__saving_energy = 0.0
        self.__core_energy = defaultdict(float)
        self.__router_energy = defaultdict(float)

    @property
    def num_chips(self):
        """
        The total number of chips used.

        :rtype: int
        """
        return self.__num_chips

    @num_chips.setter
    def num_chips(self, value):
        self.__num_chips = int(value)

    @property
    def num_cores(self):
        """
        The total number of cores used, including for SCAMP.

        :rtype: int
        """
        return self.__num_cores

    @num_cores.setter
    def num_cores(self, value):
        self.__num_cores = int(value)

    @property
    def num_fpgas(self):
        """
        The total number of FPGAs used.

        :rtype: int
        """
        return self.__num_fpgas

    @num_fpgas.setter
    def num_fpgas(self, value):
        self.__num_fpgas = int(value)

    @property
    def num_frames(self):
        """
        The total number of frames used.

        :rtype: int
        """
        return self.__num_frames

    @num_frames.setter
    def num_frames(self, value):
        self.__num_frames = int(value)

    @property
    def total_time_secs(self):
        """
        Time taken in total, in seconds.

        :rtype: float
        """
        return self.exec_time_secs + self.loading_time_secs + \
            self.saving_time_secs + self.data_gen_time_secs + \
            self.mapping_time_secs

    @property
    def booted_time_secs(self):
        """
        Time taken when the machine is booted, in seconds.

        :rtype: float
        """
        return self.exec_time_secs + self.loading_time_secs + \
            self.saving_time_secs

    @property
    def exec_time_secs(self):
        """
        Time taken by active simulation running, in seconds.

        :rtype: float
        """
        return self.__exec_time

    @exec_time_secs.setter
    def exec_time_secs(self, value):
        self.__exec_time = float(value)

    @property
    def mapping_time_secs(self):
        """
        Time taken by the mapping phase, in seconds.

        :rtype: float
        """
        return self.__mapping_time

    @mapping_time_secs.setter
    def mapping_time_secs(self, value):
        self.__mapping_time = float(value)

    @property
    def data_gen_time_secs(self):
        """
        Time taken by data generation phase, in seconds.

        :rtype: float
        """
        return self.__data_gen_time

    @data_gen_time_secs.setter
    def data_gen_time_secs(self, value):
        self.__data_gen_time = float(value)

    @property
    def loading_time_secs(self):
        """
        Time taken by data loading, in seconds.

        :rtype: float
        """
        return self.__loading_time

    @loading_time_secs.setter
    def loading_time_secs(self, value):
        self.__loading_time = float(value)

    @property
    def saving_time_secs(self):
        """
        Time taken by data extraction, in seconds.

        :rtype: float
        """
        return self.__saving_time

    @saving_time_secs.setter
    def saving_time_secs(self, value):
        self.__saving_time = float(value)

    @property
    def total_energy_joules(self):
        """
        Total of all energy costs, in Joules.

        :rtype: float
        """
        baseline_energy = self.baseline_joules + self.fpga_total_energy_joules
        idle_energy = self.mapping_joules + self.data_gen_joules
        active_energy = self.chip_energy_joules + self.packet_joules + \
            self.loading_joules + self.saving_joules
        return baseline_energy + idle_energy + active_energy

    @property
    def chip_energy_joules(self):
        """
        Energy used by all SpiNNaker chips during active simulation
        running, in Joules.

        :rtype: float
        """
        return self.__chip_energy

    @chip_energy_joules.setter
    def chip_energy_joules(self, value):
        self.__chip_energy = float(value)

    @property
    def fpga_total_energy_joules(self):
        """
        Energy used by all FPGAs in total, in Joules.

        :rtype: float
        """
        return self.__fpga_total_energy

    @fpga_total_energy_joules.setter
    def fpga_total_energy_joules(self, value):
        self.__fpga_total_energy = float(value)

    @property
    def fpga_exec_energy_joules(self):
        """
        Energy used by all FPGAs during active simulation running, in
        Joules. This is *included* in the total FPGA energy.

        :rtype: float
        """
        return self.__fpga_exec_energy

    @fpga_exec_energy_joules.setter
    def fpga_exec_energy_joules(self, value):
        self.__fpga_exec_energy = float(value)

    @property
    def baseline_joules(self):
        """
        Baseline/idle energy used, in Joules. This is used by things like the
        frames the SpiNNaker boards are held in, the cooling system, etc.

        :rtype: float
        """
        return self.__baseline_energy

    @baseline_joules.setter
    def baseline_joules(self, value):
        self.__baseline_energy = float(value)

    @property
    def packet_joules(self):
        """
        Energy used by packet transmission, in Joules.

        :rtype: float
        """
        return self.__packet_energy

    @packet_joules.setter
    def packet_joules(self, value):
        self.__packet_energy = float(value)

    @property
    def mapping_joules(self):
        """
        Energy used during the mapping phase, in Joules. Assumes that
        the SpiNNaker system has been shut down.

        :rtype: float
        """
        return self.__mapping_energy

    @mapping_joules.setter
    def mapping_joules(self, value):
        self.__mapping_energy = float(value)

    @property
    def data_gen_joules(self):
        """
        Energy used during the data generation phase, in Joules. Assumes
        that the SpiNNaker system has been shut down.

        :rtype: float
        """
        return self.__data_gen_energy

    @data_gen_joules.setter
    def data_gen_joules(self, value):
        self.__data_gen_energy = float(value)

    @property
    def loading_joules(self):
        """
        Energy used during data loading, in Joules.

        :rtype: float
        """
        return self.__loading_energy

    @loading_joules.setter
    def loading_joules(self, value):
        self.__loading_energy = float(value)

    @property
    def saving_joules(self):
        """
        Energy used during data extraction, in Joules.

        :rtype: float
        """
        return self.__saving_energy

    @saving_joules.setter
    def saving_joules(self, value):
        self.__saving_energy = float(value)

    def get_router_active_energy_joules(self, x, y):
        """
        Energy used (above idle baseline) by a particular router, in Joules.

        Unused routers always report 0.0 for this.

        :param int x:
        :param int y:
        :rtype: float
        """
        return self.__router_energy[x, y]

    def add_router_active_energy(self, x, y, joules):
        """
        Adds energy for a particular router.
        It can be called multiple times per router.

        Only intended to be used during construction of this object.

        :param int x:
        :param int y:
        :param float joules: the energy to add for this router, in Joules.
        """
        self.__router_energy[x, y] += float(joules)

    @property
    def active_routers(self):
        """
        Enumeration of the coordinates of the routers that can report
        active energy usage.

        :rtype: iterable(tuple(int, int))
        """
        return self.__router_energy.keys()

    def get_core_active_energy_joules(self, x, y, p):
        """
        Energy used (above idle baseline) by a particular core, in Joules.

        Unused cores always report 0.0 for this.

        :param int x:
        :param int y:
        :param int p:
        :rtype: float
        """
        return self.__core_energy[x, y, p]

    def add_core_active_energy(self, x, y, p, joules):
        """
        Adds energy for a particular core.
        It can be called multiple times per core.

        Only intended to be used during construction of this object.

        :param int x:
        :param int y:
        :param int p:
        :param float joules: the energy to add for this core, in Joules.
        """
        self.__core_energy[x, y, p] += float(joules)

    @property
    def active_cores(self):
        """
        Enumeration of the coordinates of the cores that can report active
        energy usage.

        :rtype: iterable(tuple(int, int, int))
        """
        return self.__core_energy.keys()
