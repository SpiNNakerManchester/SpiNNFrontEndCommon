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

import requests
from spinn_machine import Machine
from spinn_machine.virtual_machine import virtual_machine


class HBPMaxMachineGenerator(object):
    """ Generates a virtual machine of the width and height of the maximum\
        machine a given HBP server can generate.
    """

    __slots__ = []

    def __call__(self, hbp_server_url, total_run_time,
                 max_machine_core_reduction=0):
        """
        :param str hbp_server_url:
            The URL of the HBP server from which to get the machine
        :param int total_run_time: The total run time to request
        :param int max_machine_core_reduction:
            the number of cores less than
            :py:const:`~spinn_machine.Machine.DEFAULT_MAX_CORES_PER_CHIP`
            that each chip should have
        :rtype: ~spinn_machine.Machine
        """

        max_machine = self._max_machine_request(hbp_server_url, total_run_time)

        n_cpus_per_chip = (Machine.max_cores_per_chip() -
                           max_machine_core_reduction)

        # Return the width and height and assume that it has wrap arounds
        return virtual_machine(
            width=max_machine["width"], height=max_machine["height"],
            n_cpus_per_chip=n_cpus_per_chip, validate=False)

    def _max_machine_request(self, url, total_run_time):
        """
        :param str url:
        :param int total_run_time:
        :rtype: dict
        """
        if url.endswith("/"):
            url = url[:-1]
        r = requests.get("{}/max".format(url), params={
            'runTime': total_run_time})
        r.raise_for_status()
        return r.json()
