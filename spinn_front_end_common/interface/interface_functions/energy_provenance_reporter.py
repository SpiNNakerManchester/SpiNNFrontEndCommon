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

import re
from spinn_front_end_common.utilities.utility_objs import ProvenanceDataItem

#: The simple properties of PowerUsed object to be reported
_BASIC_PROPERTIES = (
    # Counts
    "num_chips", "num_cores", "num_fpgas", "num_frames",
    # Times (in seconds)
    "total_time_secs", "booted_time_secs", "mapping_time_secs",
    "data_gen_time_secs", "loading_time_secs", "exec_time_secs",
    "saving_time_secs",
    # Energies (in Joules)
    "total_energy_joules", "baseline_joules",
    "fpga_total_energy_joules", "fpga_exec_energy_joules",
    "packet_joules", "mapping_joules", "data_gen_joules",
    "loading_joules", "chip_energy_joules", "saving_joules")
#: The main provenance key we use
_PROV_KEY = "power_provenance"


class EnergyProvenanceReporter(object):
    """ Converts the power usage information into provenance data.
    """

    __slots__ = []

    def __call__(self, power_used, placements):
        """
        :param PowerUsed power_used:
            The computed basic power consumption information
        :param ~pacman.model.placements.Placements placements:
            Used for describing what a core was actually doing
        :rtype: list(ProvenanceDataItem)
        """
        prov_items = [
            ProvenanceDataItem(
                [_PROV_KEY, self.__prop_name(prop)],
                getattr(power_used, prop))
            for prop in _BASIC_PROPERTIES]
        prov_items.extend(
            ProvenanceDataItem(
                [_PROV_KEY, self.__core_name(placements, x, y, p)],
                power_used.get_core_active_energy_joules(x, y, p))
            for x, y, p in power_used.active_cores)
        prov_items.extend(
            ProvenanceDataItem(
                [_PROV_KEY, self.__router_name(x, y)],
                power_used.get_router_active_energy_joules(x, y))
            for x, y in power_used.active_routers)
        return prov_items

    @staticmethod
    def __prop_name(name):
        name = re.sub(r"_time_secs$", r" time (seconds)", name)
        return re.sub(r"(_energy)?_joules", r" energy (Joules)", name)

    @staticmethod
    def __core_name(placements, x, y, p):
        """
        :param ~.Placements placements:
        :rtype: str
        """
        if p == 0:
            # SCAMP always runs on virtual core zero, by definition
            return "SCAMP(OS)@{},{},{} energy (Joules)".format(x, y, p)
        if placements.is_processor_occupied(x, y, p):
            vtx = placements.get_vertex_on_processor(x, y, p)
            return "{} energy (Joules)".format(vtx.label)
        return "core@{},{},{} energy (Joules)".format(x, y, p)

    @staticmethod
    def __router_name(x, y):
        return "router@{},{} energy (Joules)".format(x, y)
