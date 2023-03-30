# Copyright (c) 2016 The University of Manchester
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

from enum import IntEnum
import struct
from spinn_utilities.overrides import overrides
from pacman.model.graphs.machine import MachineVertex
from pacman.model.resources import ConstantSDRAM
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.provenance import (
    ProvidesProvenanceDataFromMachineImpl, ProvenanceWriter)
from spinn_front_end_common.interface.simulation.simulation_utilities import (
    get_simulation_header_array)
from spinn_front_end_common.abstract_models import (
    AbstractGeneratesDataSpecification, AbstractHasAssociatedBinary)
from spinn_front_end_common.utilities.utility_objs import ExecutableType
from spinn_front_end_common.utilities.constants import (
    SYSTEM_BYTES_REQUIREMENT, SIMULATION_N_BYTES, BYTES_PER_WORD)
from spinn_front_end_common.utilities.exceptions import ConfigurationException

_ONE_SHORT = struct.Struct("<H")
_TWO_BYTES = struct.Struct("<BB")


class LivePacketGatherMachineVertex(
        MachineVertex, ProvidesProvenanceDataFromMachineImpl,
        AbstractGeneratesDataSpecification, AbstractHasAssociatedBinary):
    """
    Used to gather multicast packets coming from cores and stream them
    out to a receiving application on host. Only ever deployed on chips
    with a working Ethernet connection.
    """
    class _REGIONS(IntEnum):
        SYSTEM = 0
        CONFIG = 1
        PROVENANCE = 2

    #: Used to identify tags involved with the live packet gatherer.
    TRAFFIC_IDENTIFIER = "LPG_EVENT_STREAM"

    _N_ADDITIONAL_PROVENANCE_ITEMS = 4
    _CONFIG_SIZE = 15 * BYTES_PER_WORD
    _PROVENANCE_REGION_SIZE = 2 * BYTES_PER_WORD
    KEY_ENTRY_SIZE = 3 * BYTES_PER_WORD

    def __init__(self, lpg_params, app_vertex=None, label=None):
        """
        :param LivePacketGatherParameters lpg_params: The parameters object
        :param LivePacketGather app_vertex: The application vertex
        :param str label: An optional label
        """
        # inheritance
        super().__init__(
            label or lpg_params.label, app_vertex=app_vertex)

        # app specific data items
        self._lpg_params = lpg_params
        self._incoming_sources = list()

    def add_incoming_source(self, m_vertex, partition_id):
        """
        Add a machine vertex source incoming into this gatherer.

        :param ~pacman.model.graphs.machine.MachineVertex m_vertex:
            The source machine vertex
        :param str partition_id: The incoming partition id
        """
        self._incoming_sources.append((m_vertex, partition_id))

    @property
    @overrides(ProvidesProvenanceDataFromMachineImpl._provenance_region_id)
    def _provenance_region_id(self):
        return self._REGIONS.PROVENANCE

    @property
    @overrides(ProvidesProvenanceDataFromMachineImpl._n_additional_data_items)
    def _n_additional_data_items(self):
        return self._N_ADDITIONAL_PROVENANCE_ITEMS

    def _get_key_translation_sdram(self):
        if not self._lpg_params.translate_keys:
            return 0
        return len(self._incoming_sources) * self.KEY_ENTRY_SIZE

    @property
    @overrides(MachineVertex.sdram_required)
    def sdram_required(self):
        return ConstantSDRAM(
            self.get_sdram_usage() + self._get_key_translation_sdram())

    @property
    @overrides(MachineVertex.iptags)
    def iptags(self):
        return [self._lpg_params.get_iptag_resource()]

    @overrides(
        ProvidesProvenanceDataFromMachineImpl.parse_extra_provenance_items)
    def parse_extra_provenance_items(self, label, x, y, p, provenance_data):
        (lost, lost_payload, events, messages) = provenance_data

        with ProvenanceWriter() as db:
            db.insert_core(x, y, p, "lost_packets_without_payload", lost)
            if lost > 0:
                db.insert_report(
                    f"The {label} has lost {lost} packets which do "
                    "not have payloads during its execution. "
                    "Try increasing the machine time step or increasing the "
                    "time scale factor. If you are running in real time, "
                    "try reducing the number of vertices which are feeding "
                    "this live packet gatherer")

            db.insert_core(x, y, p, "lost_packets_with_payload", lost_payload)
            if lost_payload > 0:
                db.insert_report(
                    f"The {label} has lost {lost_payload} packets "
                    "which have payloads during its execution. "
                    "Try increasing the machine time step or increasing the "
                    "time scale factor. If you are running in real time, "
                    "try reducing the number of vertices which are feeding "
                    "this live packet gatherer")

            db.insert_core(x, y, p, "gathered_events", events)

            db.insert_core(x, y, p, "messages_sent_to_host", messages)

    @overrides(AbstractHasAssociatedBinary.get_binary_file_name)
    def get_binary_file_name(self):
        return 'live_packet_gather.aplx'

    @overrides(AbstractHasAssociatedBinary.get_binary_start_type)
    def get_binary_start_type(self):
        return ExecutableType.USES_SIMULATION_INTERFACE

    @overrides(
        AbstractGeneratesDataSpecification.generate_data_specification)
    def generate_data_specification(
            self, spec, placement):  # @UnusedVariable
        # pylint: disable=arguments-differ
        spec.comment("\n*** Spec for LivePacketGather Instance ***\n\n")

        # Construct the data images needed for the Neuron:
        self._reserve_memory_regions(spec)
        self._write_setup_info(spec)
        self._write_configuration_region(
            spec, FecDataView.get_tags().get_ip_tags_for_vertex(self))

        # End-of-Spec:
        spec.end_specification()

    def _reserve_memory_regions(self, spec):
        """
        Reserve SDRAM space for memory areas.

        :param ~.DataSpecificationGenerator spec:
        """
        spec.comment("\nReserving memory space for data regions:\n\n")

        # Reserve memory:
        spec.reserve_memory_region(
            region=self._REGIONS.SYSTEM,
            size=SIMULATION_N_BYTES, label='system')
        spec.reserve_memory_region(
            region=self._REGIONS.CONFIG,
            size=self._CONFIG_SIZE + self._get_key_translation_sdram(),
            label='config')
        self.reserve_provenance_data_region(spec)

    def _write_configuration_region(self, spec, iptags):
        """
        Write the configuration region to the spec.

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

        # Received key mask
        spec.write_value(self._lpg_params.received_key_mask)

        # Translated key right shift
        spec.write_value(self._lpg_params.translated_key_right_shift)

        # Key Translation
        if not self._lpg_params.translate_keys:
            spec.write_value(0)
        else:
            routing_info = FecDataView.get_routing_infos()
            spec.write_value(len(self._incoming_sources))
            for vertex, partition_id in self._incoming_sources:
                r_info = routing_info.get_routing_info_from_pre_vertex(
                    vertex, partition_id)
                spec.write_value(r_info.key)
                spec.write_value(r_info.mask)
                spec.write_value(vertex.vertex_slice.lo_atom)

    def _write_setup_info(self, spec):
        """
        Write basic info to the system region.

        :param ~.DataSpecificationGenerator spec:
        """
        # Write this to the system region (to be picked up by the simulation):
        spec.switch_write_focus(region=self._REGIONS.SYSTEM)
        spec.write_array(get_simulation_header_array(
            self.get_binary_file_name()))

    @classmethod
    def get_sdram_usage(cls):
        """
        Get the SDRAM used by this vertex.

        :rtype: int
        """
        return (
            SYSTEM_BYTES_REQUIREMENT + cls._CONFIG_SIZE +
            cls.get_provenance_data_size(cls._N_ADDITIONAL_PROVENANCE_ITEMS))

    @property
    def params(self):
        return self._lpg_params
