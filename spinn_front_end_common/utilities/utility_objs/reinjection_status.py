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

import struct
from .dpri_flags import DPRIFlags

_PATTERN = struct.Struct("<IIIIIIIIII")


def _decode_router_timeout_value(value):
    """
    Get the timeout value of a router in ticks, given an 8-bit floating
    point value stored in an int (!)

    :param int value: The value to convert
    :rtype: int
    """
    mantissa = value & 0xF
    exponent = (value >> 4) & 0xF
    if exponent <= 4:
        return ((mantissa + 16) - (2 ** (4 - exponent))) * (2 ** exponent)
    return (mantissa + 16) * (2 ** exponent)


class ReInjectionStatus(object):
    """
    Represents a status information report from dropped packet reinjection.
    """

    __slots__ = (

        # The WAIT1 timeout value of the router in cycles
        "_wait1_timeout",

        # The WAIT2 timeout value of the router in cycles
        "_wait2_timeout",

        # The number of packets dropped by the router and received by\
        # the re injection functionality (may not fit in the queue though)
        "_n_dropped_packets",

        # The number of times that when a dropped packet was read it was\
        #    found that another one or more packets had also been dropped,\
        #    but had been missed
        "_n_missed_dropped_packets",

        # Of the n_dropped_packets received, how many were lost due to not\
        #    having enough space in the queue of packets to reinject
        "_n_dropped_packet_overflows",

        # Of the n_dropped_packets received, how many packets were\
        #    successfully re-injected
        "_n_reinjected_packets",

        # The number of times that when a dropped packet was caused due to\
        # a link failing to take the packet.
        "_n_link_dumps",

        # The number of times that when a dropped packet was caused due to\
        # a processor failing to take the packet.
        "_n_processor_dumps",

        # the flags that states which types of packets were being recorded
        "_flags",

        # Indicates the links or processors dropped from
        "_link_proc_bits"
    )

    def __init__(self, data, offset):
        """
        :param bytes data: The data containing the information
        :param int offset: The offset in the data where the information starts
        """
        (self._wait1_timeout, self._wait2_timeout,
         self._n_dropped_packets, self._n_missed_dropped_packets,
         self._n_dropped_packet_overflows, self._n_reinjected_packets,
         self._n_link_dumps, self._n_processor_dumps, self._flags,
         self._link_proc_bits) = _PATTERN.unpack_from(data, offset)

    @property
    def router_wait1_timeout(self):
        """
        The WAIT1 timeout value of the router, in cycles.

        :rtype: int
        """
        return _decode_router_timeout_value(self._wait1_timeout)

    @property
    def router_wait1_timeout_parameters(self):
        """
        The WAIT1 timeout value of the router as mantissa and exponent.

        :rtype: tuple(int,int)
        """
        mantissa = self._wait1_timeout & 0xF
        exponent = (self._wait1_timeout >> 4) & 0xF
        return mantissa, exponent

    @property
    def router_wait2_timeout(self):
        """
        The WAIT2 timeout value of the router, in cycles.

        :rtype: int
        """
        return _decode_router_timeout_value(self._wait2_timeout)

    @property
    def router_wait2_timeout_parameters(self):
        """
        The WAIT2 timeout value of the router as mantissa and exponent.

        :rtype: tuple(int,int)
        """
        mantissa = self._wait2_timeout & 0xF
        exponent = (self._wait2_timeout >> 4) & 0xF
        return mantissa, exponent

    @property
    def n_dropped_packets(self):
        """
        The number of packets dropped by the router and received by
        the reinjection functionality (may not fit in the queue though).

        :rtype: int
        """
        return self._n_dropped_packets

    @property
    def n_missed_dropped_packets(self):
        """
        The number of times that when a dropped packet was read it was
        found that another one or more packets had also been dropped,
        but had been missed.

        :rtype: int
        """
        return self._n_missed_dropped_packets

    @property
    def n_dropped_packet_overflows(self):
        """
        Of the n_dropped_packets received, how many were lost due to not
        having enough space in the queue of packets to reinject.

        :rtype: int
        """
        return self._n_dropped_packet_overflows

    @property
    def n_processor_dumps(self):
        """
        The number of times that when a dropped packet was caused due to
        a processor failing to take the packet.

        :rtype: int
        """
        return self._n_processor_dumps

    @property
    def n_link_dumps(self):
        """
        The number of times that when a dropped packet was caused due to
        a link failing to take the packet.

        :rtype: int
        """
        return self._n_link_dumps

    @property
    def n_reinjected_packets(self):
        """
        Of the n_dropped_packets received, how many packets were
        successfully re-injected.

        :rtype: int
        """
        return self._n_reinjected_packets

    def _flag_set(self, flag):
        return (self._flags & flag.value) != 0

    @property
    def is_reinjecting_multicast(self):
        """
        True if re-injection of multicast packets is enabled.

        :rtype: bool
        """
        return self._flag_set(DPRIFlags.MULTICAST)

    @property
    def is_reinjecting_point_to_point(self):
        """
        True if re-injection of point-to-point packets is enabled.

        :rtype: bool
        """
        return self._flag_set(DPRIFlags.POINT_TO_POINT)

    @property
    def is_reinjecting_nearest_neighbour(self):
        """
        True if re-injection of nearest neighbour packets is enabled.

        :rtype: bool
        """
        return self._flag_set(DPRIFlags.NEAREST_NEIGHBOUR)

    @property
    def is_reinjecting_fixed_route(self):
        """
        True if re-injection of fixed-route packets is enabled.

        :rtype: bool
        """
        return self._flag_set(DPRIFlags.FIXED_ROUTE)

    @property
    def links_dropped_from(self):
        return [
            link for link in range(6) if self._link_proc_bits & (1 << link)]

    @property
    def processors_dropped_from(self):
        return [
            p for p in range(18) if self._link_proc_bits & (1 << p + 6)]
