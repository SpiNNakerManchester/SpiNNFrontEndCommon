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

from enum import IntEnum
import struct
from spinn_utilities.overrides import overrides
from pacman.executor.injection_decorator import inject_items
from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import (
    ConstantSDRAM, CPUCyclesPerTickResource, DTCMResource, ResourceContainer)
from spinn_front_end_common.interface.provenance import (
    ProvidesProvenanceDataFromMachineImpl)
from spinn_front_end_common.interface.simulation.simulation_utilities import (
    get_simulation_header_array)
from spinn_front_end_common.abstract_models import (
    AbstractGeneratesDataSpecification, AbstractHasAssociatedBinary,
    AbstractSupportsDatabaseInjection)
from spinn_front_end_common.utilities.utility_objs import (
    ProvenanceDataItem, ExecutableType)
from spinn_front_end_common.utilities.constants import (
    SYSTEM_BYTES_REQUIREMENT, SIMULATION_N_BYTES, BYTES_PER_WORD)
from spinn_front_end_common.utilities.exceptions import ConfigurationException

_ONE_SHORT = struct.Struct("<H")
_TWO_BYTES = struct.Struct("<BB")


class LivePacketGatherMachineVertex(
        MachineVertex, ProvidesProvenanceDataFromMachineImpl,
        AbstractGeneratesDataSpecification, AbstractHasAssociatedBinary,
        AbstractSupportsDatabaseInjection):
    """ Used to gather multicast packets coming from cores and stream them \
        out to a receiving application on host. Only ever deployed on chips \
        with a working Ethernet connection.
    """
    class _REGIONS(IntEnum):
        SYSTEM = 0
        CONFIG = 1
        PROVENANCE = 2

    #: Used to identify tags involved with the live packet gatherer.
    TRAFFIC_IDENTIFIER = "LPG_EVENT_STREAM"

    _N_ADDITIONAL_PROVENANCE_ITEMS = 4
    _CONFIG_SIZE = 12 * BYTES_PER_WORD
    _PROVENANCE_REGION_SIZE = 2 * BYTES_PER_WORD

    def __init__(
            self, lpg_params, constraints=None, app_vertex=None, label=None):
        """
        :param LivePacketGatherParameters lpg_params:
        :param LivePacketGather app_vertex:
        :param str label:
        :param constraints:
        :type constraints:
            iterable(~pacman.model.constraints.AbstractConstraint)
        """
        # inheritance
        super(LivePacketGatherMachineVertex, self).__init__(
            label or lpg_params.label, constraints=constraints,
            app_vertex=app_vertex)

        self._resources_required = ResourceContainer(
            cpu_cycles=CPUCyclesPerTickResource(self.get_cpu_usage()),
            dtcm=DTCMResource(self.get_dtcm_usage()),
            sdram=ConstantSDRAM(self.get_sdram_usage()),
            iptags=[lpg_params.get_iptag_resource()])

        # app specific data items
        self._lpg_params = lpg_params

    @property
    @overrides(ProvidesProvenanceDataFromMachineImpl._provenance_region_id)
    def _provenance_region_id(self):
        return self._REGIONS.PROVENANCE

    @property
    @overrides(ProvidesProvenanceDataFromMachineImpl._n_additional_data_items)
    def _n_additional_data_items(self):
        return self._N_ADDITIONAL_PROVENANCE_ITEMS

    @property
    @overrides(MachineVertex.resources_required)
    def resources_required(self):
        return self._resources_required

    @property
    @overrides(AbstractSupportsDatabaseInjection.is_in_injection_mode)
    def is_in_injection_mode(self):
        return True

    @overrides(
        ProvidesProvenanceDataFromMachineImpl._get_extra_provenance_items)
    def _get_extra_provenance_items(
            self, label, location, names, provenance_data):
        # pylint: disable=unused-argument
        (lost, lost_payload, events, messages) = provenance_data
        yield ProvenanceDataItem(
            names + ["lost_packets_without_payload"], lost,
            report=(lost > 0),
            message=(
                "The live packet gatherer has lost {} packets which have "
                "payloads during its execution. Try increasing the machine "
                "time step or increasing the time scale factor. If you are "
                "running in real time, try reducing the number of vertices "
                "which are feeding this live packet gatherer".format(lost)))
        yield ProvenanceDataItem(
            names + ["lost_packets_with_payload"], lost_payload,
            report=(lost_payload > 0),
            message=(
                "The live packet gatherer has lost {} packets which do not "
                "have payloads during its execution. Try increasing the "
                "machine time step or increasing the time scale factor. If "
                "you are running in real time, try reducing the number of "
                "vertices which are feeding this live packet gatherer".format(
                    lost_payload)))
        yield ProvenanceDataItem(names + ["gathered_events"], events)
        yield ProvenanceDataItem(names + ["messages_sent_to_host"], messages)

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return 'live_packet_gather.aplx'

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExecutableType.USES_SIMULATION_INTERFACE

    @inject_items({
        "machine_time_step": "MachineTimeStep",
        "time_scale_factor": "TimeScaleFactor",
        "tags": "MemoryTags"})
    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification,
        additional_arguments={
            "machine_time_step", "time_scale_factor", "tags"
        })
    def generate_data_specification(
            self, spec, placement,  # @UnusedVariable
            machine_time_step, time_scale_factor, tags):
        """
        :param int machine_time_step:
        :param int time_scale_factor:
        :param ~pacman.model.tags.Tags tags:
        """
        # pylint: disable=too-many-arguments, arguments-differ
        spec.comment("\n*** Spec for LivePacketGather Instance ***\n\n")

        # Construct the data images needed for the Neuron:
        self._reserve_memory_regions(spec)
        self._write_setup_info(spec, machine_time_step, time_scale_factor)
        self._write_configuration_region(
            spec, tags.get_ip_tags_for_vertex(self))

        # End-of-Spec:
        spec.end_specification()

    def _reserve_memory_regions(self, spec):
        """ Reserve SDRAM space for memory areas.

        :param ~.DataSpecificationGenerator spec:
        """
        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory:
        spec.reserve_memory_region(
            region=self._REGIONS.SYSTEM,
            size=SIMULATION_N_BYTES, label='system')
        spec.reserve_memory_region(
            region=self._REGIONS.CONFIG,
            size=self._CONFIG_SIZE, label='config')
        self.reserve_provenance_data_region(spec)

    def _write_configuration_region(self, spec, iptags):
        """ Write the configuration region to the spec

        :param ~.DataSpecificationGenerator spec:
        :param iterable(~.IPTag) iptags:
            The set of IP tags assigned to the object
        :raise ConfigurationException: if `iptags` is empty
        :raise DataSpecificationException:
            when something goes wrong with the DSG generation
        """
        spec.switch_write_focus(region=self._REGIONS.CONFIG)

        spec.write_value(int(self._lpg_params.use_prefix))
        spec.write_value(self._lpg_params.key_prefix or 0)
        spec.write_value(self._lpg_params.prefix_type.value
                         if self._lpg_params.prefix_type else 0)
        spec.write_value(self._lpg_params.message_type.value
                         if self._lpg_params.message_type else 0)
        spec.write_value(self._lpg_params.right_shift)
        spec.write_value(int(self._lpg_params.payload_as_time_stamps))
        spec.write_value(int(self._lpg_params.use_payload_prefix))
        spec.write_value(self._lpg_params.payload_prefix or 0)
        spec.write_value(data=self._lpg_params.payload_right_shift)

        # SDP tag
        for iptag in iptags:
            spec.write_value(iptag.tag)
            spec.write_value(_ONE_SHORT.unpack(_TWO_BYTES.pack(
                iptag.destination_y, iptag.destination_x))[0])
            break
        else:
            raise ConfigurationException("no iptag provided")

        # number of packets to send per time stamp
        spec.write_value(self._lpg_params.number_of_packets_sent_per_time_step)

    def _write_setup_info(self, spec, machine_time_step, time_scale_factor):
        """ Write basic info to the system region

        :param ~.DataSpecificationGenerator spec:
        :param int machine_time_step:
        :param int time_scale_factor:
        """
        # Write this to the system region (to be picked up by the simulation):
        spec.switch_write_focus(region=self._REGIONS.SYSTEM)
        spec.write_array(get_simulation_header_array(
            self.get_binary_file_name(), machine_time_step, time_scale_factor))

    @staticmethod
    def get_cpu_usage():
        """ Get the CPU used by this vertex

        :return: 0
        :rtype: int
        """
        return 0

    @classmethod
    def get_sdram_usage(cls):
        """ Get the SDRAM used by this vertex

        :rtype: int
        """
        return (
            SYSTEM_BYTES_REQUIREMENT + cls._CONFIG_SIZE +
            cls.get_provenance_data_size(cls._N_ADDITIONAL_PROVENANCE_ITEMS))

    @classmethod
    def get_dtcm_usage(cls):
        """ Get the DTCM used by this vertex

        :rtype: int
        """
        return cls._CONFIG_SIZE
