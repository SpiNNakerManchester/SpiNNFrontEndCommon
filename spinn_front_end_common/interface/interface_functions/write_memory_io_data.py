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

import os
from spinn_utilities.progress_bar import ProgressBar
from pacman.model.graphs.application import ApplicationGraph
from pacman.model.graphs.machine import MachineGraph
from spinnman.processes.fill_process import FillDataType
from spinnman.utilities.io import MemoryIO, FileIO
from spinnman.messages.spinnaker_boot import SystemVariableDefinition as SV
from spinn_front_end_common.abstract_models import AbstractUsesMemoryIO
from spinn_front_end_common.utilities.constants import BYTES_PER_KB
from spinn_front_end_common.utilities.utility_objs import DataWritten
from spinn_front_end_common.utility_models import (
    DataSpeedUpPacketGatherMachineVertex as
    Gatherer)


class _TranscieverDelegate(object):
    __slots__ = ["_txrx", "_writer"]

    def __init__(self, transceiver, write_memory_function):
        """
        :param ~.Transceiver transceiver:
        :param callable write_memory_function:
        """
        self._txrx = transceiver
        self._writer = write_memory_function

    def write_memory(self, x, y, base_address, data, n_bytes=None, offset=0,
                     cpu=0, is_filename=False):
        if self._writer is not None:
            self._writer(
                x, y, base_address, data, n_bytes, offset, cpu, is_filename)
        else:
            self._txrx.write_memory(
                x, y, base_address, data, n_bytes, offset, cpu, is_filename)

    def read_memory(self, x, y, base_address, length, cpu=0):
        return self._txrx.read_memory(x, y, base_address, length, cpu)

    def fill_memory(
            self, x, y, base_address, repeat_value, bytes_to_fill,
            data_type=FillDataType.WORD):
        self._txrx.fill_memory(
            x, y, base_address, repeat_value, bytes_to_fill, data_type)


class WriteMemoryIOData(object):
    """ An algorithm that handles objects implementing the interface\
        :py:class:`AbstractUsesMemoryIO`. **Callable.**

    :param ~pacman.model.graphs.AbstractGraph graph: The graph to process
    :param ~pacman.model.placements.Placements placements:
        The placements of vertices of the graph
    :param int app_id: The ID of the application
    :param str report_folder: The location of data files
    :param str hostname: The host name of the machine
    :param ~spinnman.transceiver.Transceiver transceiver:
        The transceiver to write data using; if None only data files
        are written
    :param extra_monitor_cores_to_ethernet_connection_map:
        What packet gatherer is located on which ethernet chip
    :type extra_monitor_cores_to_ethernet_connection_map:
        dict(tuple(int,int), DataSpeedUpPacketGatherMachineVertex)
    :param processor_to_app_data_base_address:
        Optional existing dictionary of processor to base address
    :type processor_to_app_data_base_address:
        dict(tuple(int,int,int),DataWritten)
    :return: The mapping between processor and addresses allocated
    :rtype: dict(tuple(int,int,int),DataWritten)
    """

    __slots__ = [
        # The next tag to use by chip
        "_next_tag",
        "_data_folder", "_machine", "_monitor_map", "_txrx", "_use_monitors",
        "_app_id", "_hostname"
    ]

    def __init__(self):
        self._next_tag = dict()
        self._data_folder = None
        self._machine = None
        self._monitor_map = None
        self._txrx = None
        self._use_monitors = False
        self._app_id = 0
        self._hostname = ""

    def __call__(
            self, graph, placements, app_id, report_folder, hostname,
            transceiver=None, uses_advanced_monitors=False,
            extra_monitor_cores_to_ethernet_connection_map=None,
            processor_to_app_data_base_address=None, machine=None):
        """
        :param ~pacman.model.graphs.AbstractGraph graph:
        :param ~pacman.model.placements.Placements placements:
        :param int app_id:
        :param str report_folder:
        :param str hostname:
        :param ~spinnman.transceiver.Transceiver transceiver:
        :type extra_monitor_cores_to_ethernet_connection_map:
            dict(tuple(int,int), DataSpeedUpPacketGatherMachineVertex)
        :type processor_to_app_data_base_address:
            dict(tuple(int,int,int),DataWritten)
        :rtype: dict(tuple(int,int,int),DataWritten)
        """
        # pylint: disable=too-many-arguments
        if processor_to_app_data_base_address is None:
            processor_to_app_data_base_address = dict()
        progress = ProgressBar(
            sum(1 for _ in placements.placements), "Writing data")
        self._machine = machine
        self._txrx = transceiver
        self._use_monitors = uses_advanced_monitors
        self._monitor_map = extra_monitor_cores_to_ethernet_connection_map
        self._data_folder = report_folder
        self._hostname = hostname
        self._app_id = app_id

        if isinstance(graph, ApplicationGraph):
            for placement in progress.over(placements.placements):
                app_vertex = placement.vertex.app_vertex
                if not isinstance(app_vertex, AbstractUsesMemoryIO):
                    continue
                # select the mode of writing and therefore buffer size
                write_memory_function, _buf_size = self.__get_write_function(
                    placement.x, placement.y)
                self.__write_data_for_vertex(
                    placement, app_vertex,
                    processor_to_app_data_base_address, write_memory_function)
        elif isinstance(graph, MachineGraph):
            for placement in progress.over(placements.placements):
                if not isinstance(placement.vertex, AbstractUsesMemoryIO):
                    continue
                # select the mode of writing and therefore buffer size
                write_memory_function, _buf_size = self.__get_write_function(
                    placement.x, placement.y)
                self.__write_data_for_vertex(
                    placement, placement.vertex,
                    processor_to_app_data_base_address, write_memory_function)

        return processor_to_app_data_base_address

    def __get_write_function(self, x, y):
        """
        :param int x: The chip location
        :param int y: The chip location
        :rtype: tuple(callable,int)
        """
        # determine which function to use for writing memory
        write_memory_function = Gatherer. \
            locate_correct_write_data_function_for_chip_location(
                machine=self._machine, x=x, y=y, transceiver=self._txrx,
                uses_advanced_monitors=self._use_monitors,
                extra_monitor_cores_to_ethernet_connection_map=(
                    self._monitor_map))
        buffer_size = 256
        if self._use_monitors:
            buffer_size = 120 * 1024 * BYTES_PER_KB
        return write_memory_function, buffer_size

    def __get_used_tags(self, placement, heap_address):
        """ Get the tags that have already been used on the given chip

        :param ~.Placement placement:
            The x,y-coordinates of the chip, as a Placement
        :param int heap_address: The address of the heap to query for tags
        :return: The used tags
        :rtype: iterable(int)
        """
        for element in self._txrx.get_heap(
                placement.x, placement.y, heap=heap_address):
            if not element.is_free:
                yield element.tag

    def __remote_get_next_tag(self, placement):
        """ Get the next SDRAM tag to use for the Memory IO on a given chip

        :param ~.Placement placement:
            The x,y-coordinates of the chip, as a Placement
        :return: The next available tag
        """
        key = (placement.x, placement.y)
        if key not in self._next_tag:
            # Find the maximum tag already in use across the three areas
            max_tag = 0
            for area in (SV.sdram_heap_address, SV.system_ram_heap_address,
                         SV.system_sdram_heap_address):
                for tag in self.__get_used_tags(placement, area):
                    max_tag = max(max_tag, tag)
            self._next_tag[key] = max_tag + 1
        next_tag = self._next_tag[key]
        self._next_tag[key] = next_tag + 1
        return next_tag

    def __local_get_next_tag(self, placement):
        """ Get the next SDRAM tag to use for the File IO on a given chip

        :param ~.Placement placement:
            The x,y-coordinates of the chip, as a Placement
        :return: The next available tag
        :rtype: int
        """
        key = (placement.x, placement.y)  # could be other fields too
        next_tag = self._next_tag.get(key, 1)
        self._next_tag[key] = next_tag + 1
        return next_tag

    def __write_data_for_vertex(
            self, placement, vertex, base_address_map, write_memory_function):
        """ Write the data for the given vertex, if it supports the interface

        :param ~.Placement placement: The placement of the machine vertex
        :param AbstractUsesMemoryIO vertex:
            The vertex to write data for (might be an application vertex)
        :param dict(tuple(int,int,int),DataWritten) base_address_map:
            Dictionary of processor to base address
        :param callable write_memory_function:
            the function used to write data to spinnaker
        """
        # pylint: disable=too-many-arguments
        size = vertex.get_memory_io_data_size()
        if self._txrx is not None:
            tag = self.__remote_get_next_tag(placement)
            start_address = self._txrx.malloc_sdram(
                placement.x, placement.y, size, self._app_id, tag)
            delegate = _TranscieverDelegate(self._txrx, write_memory_function)
            with MemoryIO(delegate, placement.x, placement.y, start_address,
                          start_address + size) as io:
                vertex.write_data_to_memory_io(io, tag)
        else:
            tag = self.__local_get_next_tag(placement)
            start_address = 0
            filename = os.path.join(
                self._data_folder, "{}_data_{}_{}_{}_{}.dat".format(
                    self._hostname, placement.x, placement.y, placement.p,
                    tag))
            with FileIO(filename, 0, size) as io:
                vertex.write_data_to_memory_io(io, tag)
        base_address_map[placement.location] = \
            DataWritten(start_address, size, size)
