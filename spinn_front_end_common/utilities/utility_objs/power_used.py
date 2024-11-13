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
from typing import Any


class PowerUsed(object):
    """
    Describes the power used by a simulation.
    """

    __slots__ = (
        "__n_chips", "__n_active_chips", "__n_cores", "__n_active_cores",
        "__n_boards", "__n_frames",
        "__exec_time_s", "__mapping_time_s", "__loading_time_s",
        "__saving_time_s", "__other_time_s",
        "__exec_energy_j", "__exec_energy_cores_j", "__exec_energy_boards_j",
        "__mapping_energy_j", "__loading_energy_j", "__saving_energy_j",
        "__other_energy_j",
        )

    def __init__(
            self, n_chips: int, n_active_chips: int, n_cores: int,
            n_active_cores: int, n_boards: int, n_frames: int,
            exec_time_s: float, mapping_time_s: float, loading_time_s: float,
            saving_time_s: float, other_time_s: float,
            exec_energy_j: float, exec_energy_cores_j: float,
            exec_energy_boards_j: float, mapping_energy_j: float,
            loading_energy_j: float, saving_energy_j: float,
            other_energy_j: float) -> None:
        """
        :param n_chips: The number of chips used
        :param n_active_chips: The number of active chips used
        :param n_cores: The number of cores used
        :param n_active_cores: The number of active cores used
        :param n_boards: The number of boards used
        :param n_frames: The number of frames used
        :param exec_time_s: The execution time in seconds
        :param mapping_time_s: The mapping time in seconds
        :param loading_time_s: The loading time in seconds
        :param saving_time_s: The saving time in seconds
        :param other_time_s: The other time in seconds
        :param exec_energy_j:
            The execution energy of the whole system in Joules
        :param exec_energy_cores_j:
            The execution energy of just active cores / chips in Joules
        :param exec_energy_boards_j:
            The execution energy of the whole system except the Frames
            in Joules
        :param mapping_energy_j: The mapping energy in Joules
        :param loading_energy_j: The loading energy in Joules
        :param saving_energy_j: The saving energy in Joules
        :param other_energy_j: The other energy in Joules
        """
        self.__n_chips = n_chips
        self.__n_active_chips = n_active_chips
        self.__n_cores = n_cores
        self.__n_active_cores = n_active_cores
        self.__n_boards = n_boards
        self.__n_frames = n_frames

        self.__exec_time_s = exec_time_s
        self.__mapping_time_s = mapping_time_s
        self.__loading_time_s = loading_time_s
        self.__saving_time_s = saving_time_s
        self.__other_time_s = other_time_s

        self.__exec_energy_j = exec_energy_j
        self.__exec_energy_cores_j = exec_energy_cores_j
        self.__exec_energy_boards_j = exec_energy_boards_j
        self.__mapping_energy_j = mapping_energy_j
        self.__loading_energy_j = loading_energy_j
        self.__saving_energy_j = saving_energy_j
        self.__other_energy_j = other_energy_j

    @property
    def n_chips(self) -> int:
        """ Get the number of chips used
        """
        return self.__n_chips

    @property
    def n_active_chips(self) -> int:
        """ Get the number of active chips used
        """
        return self.__n_active_chips

    @property
    def n_cores(self) -> int:
        """ Get the number of cores used
        """
        return self.__n_cores

    @property
    def n_active_cores(self) -> int:
        """ Get the number of active cores used
        """
        return self.__n_active_cores

    @property
    def n_boards(self) -> int:
        """ Get the number of boards used
        """
        return self.__n_boards

    @property
    def n_frames(self) -> int:
        """ Get the number of frames used
        """
        return self.__n_frames

    @property
    def exec_time_s(self) -> float:
        """ Get the execution time in seconds
        """
        return self.__exec_time_s

    @property
    def mapping_time_s(self) -> float:
        """ Get the mapping time in seconds
        """
        return self.__mapping_time_s

    @property
    def loading_time_s(self) -> float:
        """ Get the loading time in seconds
        """
        return self.__loading_time_s

    @property
    def saving_time_s(self) -> float:
        """ Get the saving time in seconds
        """
        return self.__saving_time_s

    @property
    def other_time_s(self) -> float:
        """ Get the other time in seconds
        """
        return self.__other_time_s

    @property
    def total_time_s(self) -> float:
        """ Get the total time in seconds
        """
        return (
            self.__exec_time_s + self.__mapping_time_s +
            self.__loading_time_s + self.__saving_time_s +
            self.__other_time_s)

    @property
    def exec_energy_j(self) -> float:
        """ Get the execution energy of the whole system in Joules
        """
        return self.__exec_energy_j

    @property
    def exec_energy_cores_j(self) -> float:
        """ Get the execution energy of just active cores / chips in Joules
        """
        return self.__exec_energy_cores_j

    @property
    def exec_energy_boards_j(self) -> float:
        """ Get the execution energy of just the whole system except the Frames
            in Joules
        """
        return self.__exec_energy_boards_j

    @property
    def mapping_energy_j(self) -> float:
        """ Get the mapping energy in Joules
        """
        return self.__mapping_energy_j

    @property
    def loading_energy_j(self) -> float:
        """ Get the loading energy in Joules
        """
        return self.__loading_energy_j

    @property
    def saving_energy_j(self) -> float:
        """ Get the saving energy in Joules
        """
        return self.__saving_energy_j

    @property
    def other_energy_j(self) -> float:
        """ Get the other energy in Joules
        """
        return self.__other_energy_j

    @property
    def total_energy_j(self) -> float:
        """ Get the total energy in Joules
        """
        return (
            self.__exec_energy_j + self.__mapping_energy_j +
            self.__loading_energy_j + self.__saving_energy_j +
            self.__other_energy_j)

    def __sub__(self, other: Any) -> "PowerUsed":
        if not isinstance(other, PowerUsed):
            raise TypeError(
                f"Cannot subtract {type(other)} from PowerUsed")
        if self.n_chips != other.n_chips:
            raise ValueError(
                f"Cannot subtract PowerUsed with different n_chips "
                f"({self.n_chips} != {other.n_chips})")
        if self.n_active_chips != other.n_active_chips:
            raise ValueError(
                f"Cannot subtract PowerUsed with different n_active_chips "
                f"({self.n_active_chips} != {other.n_active_chips})")
        if self.n_cores != other.n_cores:
            raise ValueError(
                f"Cannot subtract PowerUsed with different n_cores "
                f"({self.n_cores} != {other.n_cores})")
        if self.n_active_cores != other.n_active_cores:
            raise ValueError(
                f"Cannot subtract PowerUsed with different n_active_cores "
                f"({self.n_active_cores} != {other.n_active_cores})")
        if self.n_boards != other.n_boards:
            raise ValueError(
                f"Cannot subtract PowerUsed with different n_boards "
                f"({self.n_boards} != {other.n_boards})")
        if self.n_frames != other.n_frames:
            raise ValueError(
                f"Cannot subtract PowerUsed with different n_frames "
                f"({self.n_frames} != {other.n_frames})")

        return PowerUsed(
            self.n_chips, self.n_active_chips, self.n_cores,
            self.n_active_cores, self.n_boards, self.n_frames,
            self.exec_time_s - other.exec_time_s,
            self.mapping_time_s - other.mapping_time_s,
            self.loading_time_s - other.loading_time_s,
            self.saving_time_s - other.saving_time_s,
            self.other_time_s - other.other_time_s,
            self.exec_energy_j - other.exec_energy_j,
            self.exec_energy_cores_j - other.exec_energy_cores_j,
            self.exec_energy_boards_j - other.exec_energy_boards_j,
            self.mapping_energy_j - other.mapping_energy_j,
            self.loading_energy_j - other.loading_energy_j,
            self.saving_energy_j - other.saving_energy_j,
            self.other_energy_j - other.other_energy_j)

    def __add__(self, other: Any) -> "PowerUsed":
        if not isinstance(other, PowerUsed):
            raise TypeError(
                f"Cannot add {type(other)} to PowerUsed")
        if self.n_chips != other.n_chips:
            raise ValueError(
                f"Cannot add PowerUsed with different n_chips "
                f"({self.n_chips} != {other.n_chips})")
        if self.n_active_chips != other.n_active_chips:
            raise ValueError(
                f"Cannot add PowerUsed with different n_active_chips "
                f"({self.n_active_chips} != {other.n_active_chips})")
        if self.n_cores != other.n_cores:
            raise ValueError(
                f"Cannot add PowerUsed with different n_cores "
                f"({self.n_cores} != {other.n_cores})")
        if self.n_active_cores != other.n_active_cores:
            raise ValueError(
                f"Cannot add PowerUsed with different n_active_cores "
                f"({self.n_active_cores} != {other.n_active_cores})")
        if self.n_boards != other.n_boards:
            raise ValueError(
                f"Cannot add PowerUsed with different n_boards "
                f"({self.n_boards} != {other.n_boards})")
        if self.n_frames != other.n_frames:
            raise ValueError(
                f"Cannot add PowerUsed with different n_frames "
                f"({self.n_frames} != {other.n_frames})")

        return PowerUsed(
            self.n_chips, self.n_active_chips, self.n_cores,
            self.n_active_cores, self.n_boards, self.n_frames,
            self.exec_time_s + other.exec_time_s,
            self.mapping_time_s + other.mapping_time_s,
            self.loading_time_s + other.loading_time_s,
            self.saving_time_s + other.saving_time_s,
            self.other_time_s + other.other_time_s,
            self.exec_energy_j + other.exec_energy_j,
            self.exec_energy_cores_j + other.exec_energy_cores_j,
            self.exec_energy_boards_j + other.exec_energy_boards_j,
            self.mapping_energy_j + other.mapping_energy_j,
            self.loading_energy_j + other.loading_energy_j,
            self.saving_energy_j + other.saving_energy_j,
            self.other_energy_j + other.other_energy_j)
