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

import sys

from pacman.model.partitioner_interfaces import LegacyPartitionerAPI
from spinn_utilities.overrides import overrides
from pacman.model.graphs.application import ApplicationVertex
from pacman.model.resources import (
    CPUCyclesPerTickResource, DTCMResource, ResourceContainer,
    ReverseIPtagResource)
from pacman.model.constraints.placer_constraints import BoardConstraint
from spinn_front_end_common.abstract_models import (
    AbstractProvidesOutgoingPartitionConstraints)
from spinn_front_end_common.abstract_models.impl import (
    ProvidesKeyToAtomMappingImpl)
from spinn_front_end_common.utilities.constants import SDP_PORTS
from .reverse_ip_tag_multicast_source_machine_vertex import (
    ReverseIPTagMulticastSourceMachineVertex)
from spinn_front_end_common.utilities.exceptions import ConfigurationException
from spinn_front_end_common.utilities import globals_variables


class ReverseIpTagMultiCastSource(
        ApplicationVertex, LegacyPartitionerAPI,
        AbstractProvidesOutgoingPartitionConstraints,
        ProvidesKeyToAtomMappingImpl):
    """ A model which will allow events to be injected into a SpiNNaker\
        machine and converted into multicast packets.
    """

    def __init__(
            self, n_keys, label=None, constraints=None,
            max_atoms_per_core=sys.maxsize,

            # General parameters
            board_address=None,

            # Live input parameters
            receive_port=None,
            receive_sdp_port=SDP_PORTS.INPUT_BUFFERING_SDP_PORT.value,
            receive_tag=None,
            receive_rate=10,

            # Key parameters
            virtual_key=None, prefix=None,
            prefix_type=None, check_keys=False,

            # Send buffer parameters
            send_buffer_times=None,
            send_buffer_partition_id=None,

            # Extra flag for input without a reserved port
            reserve_reverse_ip_tag=False,

            # Flag to indicate that data will be received to inject
            enable_injection=False,

            # splitter object
            splitter=None):
        """
        :param int n_keys:
            The number of keys to be sent via this multicast source
        :param str label: The label of this vertex
        :param constraints: Any initial constraints to this vertex
        :type constraints:
            iterable(~pacman.model.constraints.AbstractConstraint)
        :param int max_atoms_per_core:
        :param board_address: The IP address of the board on which to place
            this vertex if receiving data, either buffered or live (by
            default, any board is chosen)
        :type board_address: str or None
        :param receive_port: The port on the board that will listen for
            incoming event packets (default is to disable this feature; set a
            value to enable it)
        :type receive_port: int or None
        :param int receive_sdp_port:
            The SDP port to listen on for incoming event packets
            (defaults to 1)
        :param ~spinn_machine.tags.IPTag receive_tag:
            The IP tag to use for receiving live events
            (uses any by default)
        :param float receive_rate:
            The estimated rate of packets that will be sent by this source
        :param int virtual_key:
            The base multicast key to send received events with
            (assigned automatically by default)
        :param int prefix:
            The prefix to "or" with generated multicast keys
            (default is no prefix)
        :param ~spinnman.messages.eieio.EIEIOPrefix prefix_type:
            Whether the prefix should apply to the upper or lower half of the
            multicast keys (default is upper half)
        :param bool check_keys:
            True if the keys of received events should be verified before
            sending (default False)
        :param send_buffer_times: An array of arrays of times at which keys
            should be sent (one array for each key, default disabled)
        :type send_buffer_times:
            ~numpy.ndarray(~numpy.ndarray(numpy.int32)) or
            list(~numpy.ndarray(~numpy.int32)) or None
        :param send_buffer_partition_id: The ID of the partition containing
            the edges down which the events are to be sent
        :type send_buffer_partition_id: str or None
        :param bool reserve_reverse_ip_tag:
            Extra flag for input without a reserved port
        :param bool enable_injection:
            Flag to indicate that data will be received to inject
        :param splitter: the splitter object needed for this vertex
        :type splitter: None or AbstractSplitterCommon
        """
        # pylint: disable=too-many-arguments, too-many-locals
        super().__init__(
            label, constraints, max_atoms_per_core, splitter=splitter)

        # basic items
        self._n_atoms = self.round_n_atoms(n_keys, "n_keys")

        # Store the parameters for EIEIO
        self._board_address = board_address
        self._receive_port = receive_port
        self._receive_sdp_port = receive_sdp_port
        self._receive_tag = receive_tag
        self._receive_rate = receive_rate
        self._virtual_key = virtual_key
        self._prefix = prefix
        self._prefix_type = prefix_type
        self._check_keys = check_keys

        self._reverse_iptags = None
        if receive_port is not None or reserve_reverse_ip_tag:
            self._reverse_iptags = [ReverseIPtagResource(
                port=receive_port, sdp_port=receive_sdp_port,
                tag=receive_tag)]
            if board_address is not None:
                self.add_constraint(BoardConstraint(board_address))

        # Store the send buffering details
        self._send_buffer_times = self._validate_send_buffer_times(
            send_buffer_times)
        self._send_buffer_partition_id = send_buffer_partition_id

        # Store the buffering details
        self._reserve_reverse_ip_tag = reserve_reverse_ip_tag
        self._enable_injection = enable_injection

        # Store recording parameters
        self._is_recording = False

    def _validate_send_buffer_times(self, send_buffer_times):
        if send_buffer_times is None:
            return None
        if len(send_buffer_times) and hasattr(send_buffer_times[0], "__len__"):
            if len(send_buffer_times) != self._n_atoms:
                raise ConfigurationException(
                    "The array or arrays of times {} does not have the "
                    "expected length of {}".format(
                        send_buffer_times, self._n_atoms))
        return send_buffer_times

    @property
    @overrides(LegacyPartitionerAPI.n_atoms)
    def n_atoms(self):
        return self._n_atoms

    @overrides(LegacyPartitionerAPI.get_resources_used_by_atoms)
    def get_resources_used_by_atoms(self, vertex_slice):
        send_buffer_times = self._send_buffer_times
        if send_buffer_times is not None and len(send_buffer_times):
            if hasattr(send_buffer_times[0], "__len__"):
                send_buffer_times = send_buffer_times[
                    vertex_slice.lo_atom:vertex_slice.hi_atom + 1]
                # Check the buffer times on the slice are not empty
                n_buffer_times = 0
                for i in send_buffer_times:
                    if hasattr(i, "__len__"):
                        n_buffer_times += len(i)
                    else:
                        # assuming this must be a single integer
                        n_buffer_times += 1
                if n_buffer_times == 0:
                    send_buffer_times = None

        sim = globals_variables.get_simulator()
        container = ResourceContainer(
            sdram=ReverseIPTagMulticastSourceMachineVertex.get_sdram_usage(
                send_buffer_times, self._is_recording, sim.machine_time_step,
                self._receive_rate, vertex_slice.n_atoms),
            dtcm=DTCMResource(
                ReverseIPTagMulticastSourceMachineVertex.get_dtcm_usage()),
            cpu_cycles=CPUCyclesPerTickResource(
                ReverseIPTagMulticastSourceMachineVertex.get_cpu_usage()),
            reverse_iptags=self._reverse_iptags)
        return container

    @property
    def send_buffer_times(self):
        """ When messages will be sent.

        :rtype: ~numpy.ndarray(~numpy.ndarray(numpy.int32)) or
            list(~numpy.ndarray(~numpy.int32)) or None
        """
        return self._send_buffer_times

    @send_buffer_times.setter
    def send_buffer_times(self, send_buffer_times):
        self._send_buffer_times = send_buffer_times
        for vertex in self.machine_vertices:
            vertex_slice = vertex.vertex_slice
            send_buffer_times_to_set = self._send_buffer_times
            # pylint: disable=len-as-condition
            if (self._send_buffer_times is not None and
                    len(self._send_buffer_times)):
                if hasattr(self._send_buffer_times[0], "__len__"):
                    send_buffer_times_to_set = self._send_buffer_times[
                        vertex_slice.lo_atom:vertex_slice.hi_atom + 1]
            vertex.send_buffer_times = send_buffer_times_to_set

    def enable_recording(self, new_state=True):
        self._is_recording = new_state

    @overrides(AbstractProvidesOutgoingPartitionConstraints.
               get_outgoing_partition_constraints)
    def get_outgoing_partition_constraints(self, partition):
        return partition.pre_vertex.get_outgoing_partition_constraints(
            partition)

    @overrides(LegacyPartitionerAPI.create_machine_vertex)
    def create_machine_vertex(
            self, vertex_slice,
            resources_required,  # @UnusedVariable
            label=None, constraints=None):
        send_buffer_times = self._send_buffer_times
        if send_buffer_times is not None and len(send_buffer_times):
            if hasattr(send_buffer_times[0], "__len__"):
                send_buffer_times = send_buffer_times[
                    vertex_slice.lo_atom:vertex_slice.hi_atom + 1]
        machine_vertex = ReverseIPTagMulticastSourceMachineVertex(
            vertex_slice=vertex_slice,
            label=label, constraints=constraints, app_vertex=self,
            board_address=self._board_address,
            receive_port=self._receive_port,
            receive_sdp_port=self._receive_sdp_port,
            receive_tag=self._receive_tag,
            receive_rate=self._receive_rate,
            virtual_key=self._virtual_key, prefix=self._prefix,
            prefix_type=self._prefix_type, check_keys=self._check_keys,
            send_buffer_times=send_buffer_times,
            send_buffer_partition_id=self._send_buffer_partition_id,
            reserve_reverse_ip_tag=self._reserve_reverse_ip_tag,
            enable_injection=self._enable_injection)
        machine_vertex.enable_recording(self._is_recording)
        # Known issue with ReverseIPTagMulticastSourceMachineVertex
        if resources_required:
            assert (resources_required == machine_vertex.resources_required)
        return machine_vertex

    def __repr__(self):
        return self._label
