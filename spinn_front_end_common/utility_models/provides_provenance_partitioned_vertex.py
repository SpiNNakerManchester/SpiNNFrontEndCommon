from pacman.interfaces.abstract_provides_provenance_data import \
    AbstractProvidesProvenanceData
from pacman.model.partitioned_graph.partitioned_vertex import PartitionedVertex
from pacman.utilities.utility_objs.provenance_data_item import \
    ProvenanceDataItem

from spinn_front_end_common.utilities import exceptions
from spinn_front_end_common.utilities import constants

from data_specification import utility_calls as dsg_utility_calls

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
        app_data_base_address = transceiver.get_cpu_information_from_core(
            placement.x, placement.y, placement.p).user[0]

        # Get the provenance region base address
        provenance_data_region_base_address_offset = \
            dsg_utility_calls.get_region_base_address_offset(
                app_data_base_address, self._provenance_region_id)
        provenance_data_region_base_address_buff = \
            buffer(transceiver.read_memory(
                placement.x, placement.y,
                provenance_data_region_base_address_offset, 4))
        provenance_data_region_base_address = \
            struct.unpack("I", provenance_data_region_base_address_buff)[0]
        provenance_data_region_base_address += app_data_base_address

        # todo this was a function call, but alas the call only returned the first
        # get data from the machine
        data = buffer(transceiver.read_memory(
            placement.x, placement.y, provenance_data_region_base_address,
            constants.PROVENANCE_DATA_REGION_SIZE_IN_BYTES))
        provenance_data = struct.unpack_from("<III", data)

        transmission_event_overflow = provenance_data[
            constants.PROVENANCE_DATA_ENTRIES.TRANSMISSION_EVENT_OVERFLOW.value]
        timer_tic_queue_overloaded = provenance_data[
            constants.PROVENANCE_DATA_ENTRIES.TIMER_TIC_QUEUE_OVERLOADED.value]
        dma_queue_overloaded = provenance_data[
            constants.PROVENANCE_DATA_ENTRIES.DMA_QUEUE_OVERLOADED.value]

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
            item=timer_tic_queue_overloaded,
            name="Times_the_timer_tic_queue_was_overloaded",
            needs_reporting_to_end_user=timer_tic_queue_overloaded != 0,
            message_to_end_user=
            "The timer tic queue overloaded on {} occasions. This is "
            "often a sign that the system is running too quickly for the"
            " number of neurons per core, please increase the timer_tic "
            "or time_scale_factor or decrease the number of neurons "
            "per core.".format(timer_tic_queue_overloaded)))

        data_items.append(ProvenanceDataItem(
            item=dma_queue_overloaded,
            name="Times_the_dma_queue_was_overloaded",
            needs_reporting_to_end_user=dma_queue_overloaded != 0,
            message_to_end_user=
            "The DMA queue overloaded on {} occasions. This is "
            "often a sign that the system is running too quickly for the"
            " number of neurons per core, please increase the timer_tic "
            "or time_scale_factor or decrease the number of neurons "
            "per core.".format(timer_tic_queue_overloaded)))

        return data_items
