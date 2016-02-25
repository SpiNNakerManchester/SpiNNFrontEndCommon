from pacman.interfaces.abstract_provides_provenance_data import \
    AbstractProvidesProvenanceData
from pacman.model.partitioned_graph.partitioned_vertex import PartitionedVertex
from pacman.utilities.utility_objs.provenance_data_item import \
    ProvenanceDataItem

from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities import helpful_functions


import struct


class ProvidesProvenancePartitionedVertex(
        PartitionedVertex, AbstractProvidesProvenanceData):
    """
    ProvidesProvenancePartitionedVertex: vertex which provides basic
    provenance data
    """

    def __init__(self, resources_required, label, constraints,
                 provenance_region_id):
        PartitionedVertex.__init__(self, resources_required, label, constraints)
        AbstractProvidesProvenanceData.__init__(self)
        self._provenance_region_id = provenance_region_id

    def get_provenance_data_items(self, transceiver, placement=None):
        """
        @implements pacman.interfaces.abstract_provides_provenance_data.AbstractProvidesProvenanceData.get_provenance_data_items
        """
        if placement is None:
            raise exceptions.ConfigurationException(
                "To acquire provenance data from the live packet gatherer,"
                "you must provide a placement object that points to where the "
                "live packet gatherer resides on the spinnaker machine")

        # Get the App Data for the core
        provenance_data_region_base_address = \
            helpful_functions.locate_memory_region_for_placement(
                placement, self._provenance_region_id, transceiver)

        # todo this was a function call, but alas the call only returned the first
        # get data from the machine
        data = buffer(transceiver.read_memory(
            placement.x, placement.y, provenance_data_region_base_address,
            constants.PROVENANCE_DATA_REGION_SIZE_IN_BYTES))
        provenance_data = struct.unpack_from("<IIIII", data)

        transmission_event_overflow = provenance_data[
            constants.PROVENANCE_DATA_ENTRIES.TRANSMISSION_EVENT_OVERFLOW.value]
        callback_queue_overloaded = provenance_data[
            constants.PROVENANCE_DATA_ENTRIES.CALLBACK_QUEUE_OVERLOADED.value]
        dma_queue_overloaded = provenance_data[
            constants.PROVENANCE_DATA_ENTRIES.DMA_QUEUE_OVERLOADED.value]
        number_of_times_timer_tic_over_ran = provenance_data[
            constants.PROVENANCE_DATA_ENTRIES.TIMER_TIC_HAS_OVERRUN.value]
        max_number_of_times_timer_tic_over_ran = provenance_data[
            constants.PROVENANCE_DATA_ENTRIES.
            MAX_NUMBER_OF_TIMER_TIC_OVERRUN.value]

        # create provenance data items for returning
        data_items = list()
        data_items.append(ProvenanceDataItem(
            item=transmission_event_overflow,
            name="Times_the_transmission_of_spikes_overran",
            needs_reporting_to_end_user=transmission_event_overflow != 0,
            message_to_end_user=
            "The input buffer lost packets on {} occasions. This is "
            "often a sign that the system is running too quickly for the"
            " number of neurons per core, please increase the timer_tic "
            "or time_scale_factor or decrease the number of neurons "
            "per core.".format(transmission_event_overflow)))

        data_items.append(ProvenanceDataItem(
            item=callback_queue_overloaded,
            name="Times_the_callback_queue_was_overloaded",
            needs_reporting_to_end_user=callback_queue_overloaded != 0,
            message_to_end_user=
            "The callback queue overloaded on {} occasions. This is "
            "often a sign that the system is running too quickly for the"
            " number of neurons per core, please increase the timer_tic "
            "or time_scale_factor or decrease the number of neurons "
            "per core.".format(callback_queue_overloaded)))

        data_items.append(ProvenanceDataItem(
            item=dma_queue_overloaded,
            name="Times_the_dma_queue_was_overloaded",
            needs_reporting_to_end_user=dma_queue_overloaded != 0,
            message_to_end_user=
            "The DMA queue overloaded on {} occasions. This is "
            "often a sign that the system is running too quickly for the"
            " number of neurons per core, please increase the timer_tic "
            "or time_scale_factor or decrease the number of neurons "
            "per core.".format(dma_queue_overloaded)))

        data_items.append(ProvenanceDataItem(
            item=number_of_times_timer_tic_over_ran,
            name="Times_the_timer_tic_over_ran",
            needs_reporting_to_end_user=number_of_times_timer_tic_over_ran != 0,
            message_to_end_user=
            "A Timer tic callback was still executing when the next timer tic"
            " callback was fired off {} times. This is a sign of the system "
            "being overloaded and therefore the results are likely wrong. "
            "Please increase the timer_tic or time_scale_factor or decrease the"
            " number of neurons per core"
            .format(number_of_times_timer_tic_over_ran)))

        data_items.append(ProvenanceDataItem(
            item=max_number_of_times_timer_tic_over_ran,
            name="max_number_of_times_timer_tic_over_ran",
            needs_reporting_to_end_user=
            max_number_of_times_timer_tic_over_ran != 0,
            message_to_end_user=
            "There were {} timer tic callbacks waiting to be services at the "
            "worst level. This should be considered with the "
            "provenance data item \"Times_the_timer_tic_over_ran\"."
            " This is a sign of the system being overloaded and therefore "
            "the results are likely wrong. Please increase the timer_tic or "
            "time_scale_factor or decrease the number of neurons per core"
            .format(max_number_of_times_timer_tic_over_ran)))

        return data_items
