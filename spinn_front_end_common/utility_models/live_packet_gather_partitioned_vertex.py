from pacman.model.partitioned_graph.partitioned_vertex import PartitionedVertex

from spinn_front_end_common.interface.provenance\
    .provides_provenance_data_from_machine_impl \
    import ProvidesProvenanceDataFromMachineImpl
from spinn_front_end_common.utilities.utility_objs.provenance_data_item \
    import ProvenanceDataItem

from enum import Enum


class LivePacketGatherPartitionedVertex(
        PartitionedVertex, ProvidesProvenanceDataFromMachineImpl):

    _LIVE_DATA_GATHER_REGIONS = Enum(
        value="LIVE_DATA_GATHER_REGIONS",
        names=[('SYSTEM', 0),
               ('CONFIG', 1),
               ('PROVENANCE', 2)])

    N_ADDITIONAL_PROVENANCE_ITEMS = 2

    def __init__(self, resources_required, label, constraints=None):
        PartitionedVertex.__init__(
            self, resources_required, label, constraints=constraints)
        ProvidesProvenanceDataFromMachineImpl.__init__(
            self, self._LIVE_DATA_GATHER_REGIONS.PROVENANCE.value,
            self.N_ADDITIONAL_PROVENANCE_ITEMS)

    def get_provenance_data_from_machine(self, transceiver, placement):
        provenance_data = self._read_provenance_data(transceiver, placement)
        provenance_items = self._read_basic_provenance_items(
            provenance_data, placement)
        provenance_data = self._get_remaining_provenance_data_items(
            provenance_data)
        _, _, _, _, names = self._get_placement_details(placement)

        provenance_items.append(ProvenanceDataItem(
            self._add_name(names, "lost_packets_without_payload"),
            provenance_data[0],
            report=provenance_data[0] > 0,
            message=(
                "The live packet gatherer has lost {} packets which have "
                "payloads during its execution. Try increasing the machine "
                "time step or increasing the time scale factor. If you are "
                "running in real time, try reducing the number of vertices "
                "which are feeding this live packet gatherer".format(
                    provenance_data[0]))))
        provenance_items.append(ProvenanceDataItem(
            self._add_name(names, "lost_packets_with_payload"),
            provenance_data[1],
            report=provenance_data[1] > 0,
            message=(
                "The live packet gatherer has lost {} packets which do not "
                "have payloads during its execution. Try increasing the "
                "machine time step or increasing the time scale factor. If "
                "you are running in real time, try reducing the number of "
                "vertices which are feeding this live packet gatherer".format(
                    provenance_data[1]))))

        return provenance_items
