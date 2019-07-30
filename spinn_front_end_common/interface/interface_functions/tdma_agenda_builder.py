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

import math
from spinn_front_end_common.utilities.exceptions import ConfigurationException

_CPU_CYCLES_PER_INTERRUPT_TO_CALLBACK = 40
_CONVERSION_BETWEEN_MICRO_TO_CPU_CYCLES = 200


class TDMAAgendaBuilder(object):
    """ Algorithm that builds an agenda for transmissions. It uses a TDMA \
        (time-division multiple access) system and graph colouring to deduce\
        the agenda set up. Ensures parallel transmissions so that the\
        destination should never be overloaded.
    """

    def __call__(
            self, machine_graph, number_of_cpu_cycles_per_receive,
            other_cpu_demands_in_cpu_cycles,
            n_packets_per_time_window, machine_time_step, time_scale_factor,
            safety_factor=1):
        # pylint: disable=too-many-arguments
        time_offset = dict()

        # figure out max in edges (as this becomes the colour scheme
        max_in_edges = self._calculate_max_edges(machine_graph)

        # check its possible to make an agenda
        cpu_cycles_needed_per_window = self._check_time_window_size(
            number_of_cpu_cycles_per_receive, machine_time_step,
            time_scale_factor, n_packets_per_time_window, max_in_edges,
            safety_factor, other_cpu_demands_in_cpu_cycles)

        # do graph colouring to ensure TDMA is met
        time_offset = self._handle_colouring(
            max_in_edges, machine_graph, time_offset)

        # build the agenda
        agenda = self._build_agenda(
            machine_graph, cpu_cycles_needed_per_window, time_offset,
            n_packets_per_time_window)

        return agenda

    def _build_agenda(
            self, machine_graph, cpu_cycles_needed_per_window, time_offset,
            n_packets_per_time_window):
        """ Builds the TDMA system.

        :param machine_graph: the machine graph of the application
        :param cpu_cycles_needed_per_window:\
            how long the receive function takes
        :param time_offset: the colouring offsets
        :param n_packets_per_time_window:\
            the packets expected to be sent per window
        :return:\
            the agenda for each vertex on its time window and its offset\
            between spike transmissions
        """
        # pylint: disable=too-many-arguments
        agenda = dict()

        for vertex in machine_graph.vertices:
            position = time_offset[vertex]
            offset = cpu_cycles_needed_per_window * position
            time_between_packets = \
                cpu_cycles_needed_per_window // n_packets_per_time_window
            agenda[vertex] = dict()
            agenda[vertex]['time_offset'] = offset
            agenda[vertex]['time_between_packets'] = time_between_packets
        return agenda

    @staticmethod
    def _calculate_max_edges(machine_graph):
        """ Deduces the max incoming edges for any vertex

        :param machine_graph: the machine graph of the application
        :return:\
            the max number of incoming edges to any vertex in the application
        """
        max_in_edges = 0
        for vertex in machine_graph.vertices:
            n_incoming_edges = len(
                machine_graph.get_edges_ending_at_vertex(vertex))
            if n_incoming_edges > max_in_edges:
                max_in_edges = n_incoming_edges
        return max_in_edges

    def _handle_colouring(self, max_in_edges, machine_graph, time_offset):
        """ Operates the graph colouring greedy code.

        :param max_in_edges: the number of colours to colour the graph
        :param machine_graph:\
            the machine graph representation of the application
        :param time_offset: the dict holding vertex to time offset mapping
        :return: the dict holding vertex to time offset mapping
        """
        colours = list()
        for colour in range(0, max_in_edges + 1):  # plus 1 to include myself
            colours.append(colour)

        # use greedy colouring algorithm to colour graph
        for vertex in machine_graph.vertices:
            time_offset[vertex] = self._get_colour_for_vertex(
                vertex, machine_graph, colours, time_offset)
        return time_offset

    def _get_colour_for_vertex(
            self, vertex, machine_graph, colours, colour_mapping):
        """ Cycles though available colours

        :param vertex: the vertex in question
        :param machine_graph:\
            the machine graph representation of the application
        :param colours: the available colours for the graph colouring
        :param colour_mapping: the mapping between vertex and colour
        :return: the colour of this vertex
        """
        for colour in colours:
            if self._available(colour, vertex, machine_graph, colour_mapping):
                return colour
        raise ConfigurationException(
            "cannot colour this edge. Something screwed up")

    @staticmethod
    def _available(colour, vertex, machine_graph, colour_mapping):
        """ Checks its neighbours to see if its colour is available

        :param colour: the colour to verify against
        :param vertex: the vertex in question
        :param machine_graph:\
            the machine graph representation of the application
        :param colour_mapping: the mapping between vertex and colour
        :return: bool saying yes or no
        """
        edges = machine_graph.get_edges_ending_at_vertex(vertex)
        for edge in edges:
            post_vertex = edge.pre_vertex
            if post_vertex in colour_mapping.keys():
                if colour_mapping[post_vertex] == colour:
                    return False
        return True

    def _check_time_window_size(
            self, number_of_cpu_cycles_per_receive, machine_time_step,
            time_scale_factor, n_packets_per_time_window, max_in_edges,
            safety_factor, other_cpu_demands_in_cpu_cycles):
        """ Calculates the CPU cycles per window, and therefore verifies if\
            there is enough time to do so with a end user safety margin

        :param number_of_cpu_cycles_per_receive:\
            how long the packet reception callback takes in CPU cycles
        :param machine_time_step: the timer tick in microseconds
        :param time_scale_factor:\
            the multiplicative factor on the machine time step.
        :param n_packets_per_time_window:\
            how many packets are to be sent per time window
        :param max_in_edges:\
            the max number of edges going into any vertex in the machine graph
        :param safety_factor: the end user safely factor
        :param other_cpu_demands_in_cpu_cycles:\
            extra costs (e.g. timer tick callback etc.)
        :return: CPU cycles available per window.
        :rtype: float
        :raises ConfigurationException:\
            if the overall time is below what is possible to receive packets\
            with
        """
        # pylint: disable=too-many-arguments

        # figure out if its feasible for window to work
        total_cycles_available = \
            machine_time_step * time_scale_factor * \
            _CONVERSION_BETWEEN_MICRO_TO_CPU_CYCLES

        cpu_cycles_needed_per_window = math.ceil(
            (number_of_cpu_cycles_per_receive +
                _CPU_CYCLES_PER_INTERRUPT_TO_CALLBACK) *
            (n_packets_per_time_window + safety_factor))

        time_needed_per_epoch = \
            (cpu_cycles_needed_per_window * max_in_edges) + \
            other_cpu_demands_in_cpu_cycles

        if total_cycles_available < time_needed_per_epoch:
            raise ConfigurationException(
                "Cannot create a window for this simulation with its "
                "combined machine_time_step, time_scale_factor, and time "
                "needed per packet receive and the number of edges going to "
                "a core. Recommend reducing the graph connectivity, "
                "or increasing the machine time step or the time scale "
                "factor.\n\n"
                "Assuming same connectivity, the best current available "
                "would be {} machine_time_steps with a timescale factor of "
                "1".format(time_needed_per_epoch))
        return cpu_cycles_needed_per_window
