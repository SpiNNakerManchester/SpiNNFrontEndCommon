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


class PowerUsed(object):
    """ Describes the power used by a simulation.
    """

    __slots__ = []

    def __init__(self):
        pass

    @property
    def num_chips(self):
        """ The total number of chips used.

        :rtype: int
        """
        pass

    @property
    def num_fpgas(self):
        """ The total number of FPGAs used.

        :rtype: int
        """
        pass

    # -------------------------------------

    @property
    def exec_time_ms(self):
        """ Time taken by active simulation running, in milliseconds.

        :rtype: float
        """
        pass

    @property
    def total_time_ms(self):
        """ Time taken overall, in milliseconds.

        :rtype: float
        """
        pass

    @property
    def mapping_time_ms(self):
        """ Time taken by the mapping phase, in milliseconds.

        :rtype: float
        """
        pass

    @property
    def data_gen_time_ms(self):
        """ Time taken by data generation phase, in milliseconds.

        :rtype: float
        """
        pass

    @property
    def loading_time_ms(self):
        """ Time taken by data loading, in milliseconds.

        :rtype: float
        """
        pass

    @property
    def saving_time_ms(self):
        """ Time taken by data extraction, in milliseconds.

        :rtype: float
        """
        pass

    # -------------------------------------

    @property
    def chip_energy_joules(self):
        """ Energy used by all SpiNNaker chips during active simulation\
            running, in Joules.

        :rtype: float
        """
        pass

    @property
    def fpga_total_energy_joules(self):
        """ Energy used by all FPGAs in total, in Joules.

        :rtype: float
        """
        pass

    @property
    def fpga_exec_energy_joules(self):
        """ Energy used by all FPGAs during active simulation running, in\
            Joules.

        :rtype: float
        """
        pass

    @property
    def baseline_joules(self):
        """ Baseline/idle energy used, in Joules.

        :rtype: float
        """
        pass

    @property
    def packet_joules(self):
        """ Energy used by packet transmission, in Joules.

        :rtype: float
        """
        pass

    @property
    def mapping_joules(self):
        """ Energy used during the mapping phase, in Joules. Assumes that\
            the SpiNNaker system has been shut down.

        :rtype: float
        """
        pass

    @property
    def data_gen_joules(self):
        """ Energy used during the data generation phase, in Joules. Assumes\
            that the SpiNNaker system has been shut down.

        :rtype: float
        """
        pass

    @property
    def loading_joules(self):
        """ Energy used during data loading, in Joules.

        :rtype: float
        """
        pass

    @property
    def saving_joules(self):
        """ Energy used during data extraction, in Joules.

        :rtype: float
        """
        pass

    def get_core_active_energy_joules(self, x, y, p):
        """ Energy used (above idle baseline) by a particular core, in Joules.

        Unused cores always report 0.0 for this.

        :param int x:
        :param int y:
        :param int p:
        :rtype: float
        """
        pass
