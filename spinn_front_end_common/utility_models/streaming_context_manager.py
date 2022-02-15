# Copyright (c) 2017-2022 The University of Manchester
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


class StreamingContextManager(object):
    """ The implementation of the context manager object for streaming \
        configuration control.
    """
    __slots__ = ["_gatherers", "_monitors", "_placements", "_txrx"]

    def __init__(self, gatherers, txrx, monitors, placements):
        """
        :param iterable(DataSpeedUpPacketGatherMachineVertex) gatherers:
        :param ~spinnman.transceiver.Transceiver txrx:
        :param list(ExtraMonitorSupportMachineVertex) monitors:
        :param ~pacman.model.placements.Placements placements:
        """
        self._gatherers = list(gatherers)
        self._txrx = txrx
        self._monitors = monitors
        self._placements = placements

    def __enter__(self):
        for gatherer in self._gatherers:
            gatherer.load_system_routing_tables(
                self._txrx, self._monitors, self._placements)
        for gatherer in self._gatherers:
            gatherer.set_cores_for_data_streaming(
                self._txrx, self._monitors, self._placements)

    def __exit__(self, _type, _value, _tb):
        for gatherer in self._gatherers:
            gatherer.unset_cores_for_data_streaming(
                self._txrx, self._monitors, self._placements)
        for gatherer in self._gatherers:
            gatherer.load_application_routing_tables(
                self._txrx, self._monitors, self._placements)
        return False
