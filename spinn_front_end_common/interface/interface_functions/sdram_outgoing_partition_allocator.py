from pacman.model.graphs.abstract_sdram_partition import AbstractSDRAMPartition
from spinn_utilities.progress_bar import ProgressBar


class SDRAMOutgoingPartitionAllocator(object):

    def __call__(self, machine_graph, transceiver, placements, app_id):

        progress_bar = ProgressBar(
            total_number_of_things_to_do=len(
                machine_graph.outgoing_edge_partitions),
            string_describing_what_being_progressed=(
                "Allocating SDRAM for SDRAM outgoing egde partitions"))

        for outgoing_edge_partition in \
                progress_bar.over(machine_graph.outgoing_edge_partitions):
            if isinstance(outgoing_edge_partition, AbstractSDRAMPartition):
                placement = placements.get_placement_of_vertex(
                    outgoing_edge_partition.pre_vertex)
                sdram_base_address = transceiver.malloc_sdram(
                    placement.x, placement.y,
                    outgoing_edge_partition.total_sdram_requirements(), app_id)
                outgoing_edge_partition.sdram_base_address = sdram_base_address
