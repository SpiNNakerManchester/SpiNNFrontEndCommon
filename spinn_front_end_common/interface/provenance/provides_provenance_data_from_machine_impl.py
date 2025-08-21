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

from typing import Sequence, Tuple

from spinn_utilities.abstract_base import abstractmethod
from spinn_utilities.overrides import overrides

from spinnman.transceiver import Transceiver

from pacman.model.placements import Placement

from spinn_front_end_common.utilities.helpful_functions import (
    get_region_base_address_offset)
from spinn_front_end_common.data import FecDataView
from spinn_front_end_common.interface.ds import DataSpecificationGenerator
from spinn_front_end_common.utilities.constants import BYTES_PER_WORD
from spinn_front_end_common.utilities.helpful_functions import n_word_struct

from .abstract_provides_provenance_data_from_machine import (
    AbstractProvidesProvenanceDataFromMachine)
from .provenance_writer import ProvenanceWriter
# mypy: disable-error-code=empty-body


class ProvidesProvenanceDataFromMachineImpl(
        AbstractProvidesProvenanceDataFromMachine,
        allow_derivation=True):  # type: ignore [call-arg]
    """
    An implementation that gets provenance data from a region of integers on
    the machine.
    """

    __slots__ = ()

    N_SYSTEM_PROVENANCE_WORDS = 6

    _TIMER_TICK_OVERRUN = "Times_the_timer_tic_over_ran"
    _MAX_TIMER_TICK_OVERRUN = "Max_number_of_times_timer_tic_over_ran"
    _TIMES_DMA_QUEUE_OVERLOADED = "Times_the_dma_queue_was_overloaded"
    _TIMES_USER_QUEUE_OVERLOADED = "Times_the_user_queue_was_overloaded"
    _TIMES_TRANSMISSION_SPIKES_OVERRAN = \
        "Times_the_transmission_of_spikes_overran"
    _TIMES_CALLBACK_QUEUE_OVERLOADED = \
        "Times_the_callback_queue_was_overloaded"

    @property
    @abstractmethod
    def _provenance_region_id(self) -> int:
        """
        The index of the provenance region.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def _n_additional_data_items(self) -> int:
        """
        The number of extra machine words of provenance that the model reports.
        """
        raise NotImplementedError

    def reserve_provenance_data_region(
            self, spec: DataSpecificationGenerator) -> None:
        """
        Insert command to reserve a memory region.

        :param spec: The data specification being written.
        """
        spec.reserve_memory_region(
            self._provenance_region_id,
            self.get_provenance_data_size(self._n_additional_data_items),
            label="Provenance")

    @classmethod
    def get_provenance_data_size(cls, n_additional_data_items: int) -> int:
        """
        :param n_additional_data_items:
        :returns: Size of the provenance data to read
        """
        return (
            (cls.N_SYSTEM_PROVENANCE_WORDS + n_additional_data_items)
            * BYTES_PER_WORD)

    def _get_provenance_region_address(
            self, transceiver: Transceiver, placement: Placement) -> int:
        # Get the App Data for the core
        region_table_address = transceiver.get_region_base_address(
            placement.x, placement.y, placement.p)

        # Get the provenance region base address
        prov_region_entry_address = get_region_base_address_offset(
            region_table_address, self._provenance_region_id)
        return transceiver.read_word(
            placement.x, placement.y, prov_region_entry_address)

    def _read_provenance_data(self, placement: Placement) -> Sequence[int]:
        transceiver = FecDataView.get_transceiver()
        provenance_address = self._get_provenance_region_address(
            transceiver, placement)
        data = transceiver.read_memory(
            placement.x, placement.y, provenance_address,
            self.get_provenance_data_size(self._n_additional_data_items))
        return n_word_struct(
            self.N_SYSTEM_PROVENANCE_WORDS +
            self._n_additional_data_items).unpack_from(data)

    @staticmethod
    def _get_provenance_placement_description(
            placement: Placement) -> Tuple[str, int, int, int]:
        """
        :param placement:
        :returns:
            A descriptive (human-readable) label and the (x, y, p) coordinates
            for provenance items from the given placement.
        """
        x, y, p = placement.x, placement.y, placement.p
        desc_label = f"{placement.vertex.label} on {x},{y},{p}"
        return desc_label, x, y, p

    def parse_system_provenance_items(
            self, label: str, x: int, y: int, p: int,
            provenance_data: Sequence[int]) -> None:
        """
        Given some words of provenance data, convert the portion of them that
        describes the system provenance into proper provenance items.

        Called by
        :py:meth:`~spinn_front_end_common.interface.provenance.ProvidesProvenanceDataFromMachineImpl.parse_extra_provenance_items.get_provenance_data_from_machine`

        :param label:
            A descriptive label for the vertex (derived from label and placed
            position) to be used for provenance error reporting to the user.
        :param x: x coordinate of the chip where this core
        :param y: y coordinate of the core where this core
        :param p: virtual id of the core
        :param provenance_data:
        """
        (tx_overflow, cb_overload, dma_overload, user_overload, tic_overruns,
         tic_overrun_max) = provenance_data[:self.N_SYSTEM_PROVENANCE_WORDS]

        # save provenance data items
        with ProvenanceWriter() as db:
            db.insert_core(
                x, y, p, self._TIMES_TRANSMISSION_SPIKES_OVERRAN, tx_overflow)
            if tx_overflow != 0:
                db.insert_report(
                    f"The transmission buffer for {label} was blocked on "
                    f"{tx_overflow} occasions. "
                    f" This is often a sign that the system is experiencing "
                    f"back pressure from the communication fabric. "
                    "Please either: "
                    "1. spread the load over more cores, "
                    "2. reduce your peak transmission load, or "
                    "3. adjust your mapping algorithm.")

            db.insert_core(
                x, y, p, self._TIMES_CALLBACK_QUEUE_OVERLOADED, cb_overload)
            if cb_overload != 0:
                db.insert_report(
                    f"The callback queue for {label} overloaded on "
                    f"{cb_overload} occasions.  "
                    f"This is often a sign that the system is running "
                    "too quickly for the number of neurons per core. "
                    "Please increase the machine time step or "
                    "time_scale_factor "
                    "or decrease the number of neurons per core.")

            db.insert_core(
                x, y, p, self._TIMES_DMA_QUEUE_OVERLOADED, dma_overload)
            if dma_overload != 0:
                db.insert_report(
                    f"The DMA queue for {label} overloaded on {dma_overload} "
                    "occasions.  "
                    "This is often a sign that the system is running "
                    "too quickly for the number of neurons per core.  "
                    "Please increase the machine time step or "
                    "time_scale_factor "
                    "or decrease the number of neurons per core.")

            db.insert_core(
                x, y, p, self._TIMES_USER_QUEUE_OVERLOADED, user_overload)
            if user_overload != 0:
                db.insert_report(
                    f"The USER queue for {label} overloaded on "
                    f"{user_overload} occasions.  "
                    f"This is often a sign that the system is running too "
                    f"quickly for the number of neurons per core.  Please "
                    f"increase the machine time step or time_scale_factor "
                    "or decrease the number of neurons per core.")

            db.insert_core(
                x, y, p, self._TIMER_TICK_OVERRUN, tic_overruns)
            if tic_overruns != 0:
                db.insert_report(
                    f"A Timer tick callback in {label} was still executing "
                    f"when the next timer tick callback was fired off "
                    f"{tic_overruns} times.  "
                    f"This is a sign of the system being overloaded and "
                    f"therefore the results are likely incorrect.  Please "
                    f"increase the machine time step or time_scale_factor "
                    f"or decrease the number of neurons per core")

            db.insert_core(
                x, y, p, self._MAX_TIMER_TICK_OVERRUN, tic_overrun_max)
            if tic_overrun_max > 0:
                db.insert_report(
                    f"The timer for {label} fell behind by up to "
                    f"{tic_overrun_max} ticks.  This is a sign of the system "
                    f"being overloaded and therefore the results are likely "
                    f"incorrect. Please increase the machine time step or "
                    f"time_scale_factor "
                    f"or decrease the number of neurons per core")

    def _get_extra_provenance_words(
            self, provenance_data: Sequence[int]) -> Sequence[int]:
        """
        Gets the words of provenance data not used for system provenance.

        :param provenance_data:
        """
        return provenance_data[self.N_SYSTEM_PROVENANCE_WORDS:]

    def parse_extra_provenance_items(
            self, label: str, x: int, y: int, p: int,
            provenance_data: Sequence[int]) -> None:
        """
        Convert the remaining provenance words (those not in the standard set)
        into provenance items.

        Called by
        :py:meth:`~spinn_front_end_common.interface.provenance.ProvidesProvenanceDataFromMachineImpl.parse_extra_provenance_items.get_provenance_data_from_machine`

        :param label:
            A descriptive label for the vertex (derived from label and placed
            position) to be used for provenance error reporting to the user.
        :param x: x coordinate of the chip where this core
        :param y: y coordinate of the core where this core
        :param p: virtual id of the core
        :param provenance_data:
            The list of words of raw provenance data.
        """
        if self._n_additional_data_items:
            _ = (label, x, y, p, provenance_data)
            raise NotImplementedError(
                f"{self} provides {self._n_additional_data_items} but doesn't "
                "parse them")

    @overrides(
        AbstractProvidesProvenanceDataFromMachine.
        get_provenance_data_from_machine,
        extend_doc=False)
    def get_provenance_data_from_machine(self, placement: Placement) -> None:
        """
        Retrieve the provenance data.

        :param placement:
            Which vertex are we retrieving from, and where was it
        """
        provenance_data = self._read_provenance_data(placement)
        label, x, y, p = self._get_provenance_placement_description(placement)
        self.parse_system_provenance_items(
            label, x, y, p, provenance_data)
        self.parse_extra_provenance_items(
            label, x, y, p, self._get_extra_provenance_words(provenance_data))
