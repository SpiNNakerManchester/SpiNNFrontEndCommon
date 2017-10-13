from spinn_front_end_common.abstract_models import \
    AbstractProvidesNKeysForPartition
from spinn_front_end_common.utilities import constants
from spinn_utilities.overrides import overrides


class AbstractUtilitiesDataSpeedUpExtractor(
        AbstractProvidesNKeysForPartition):

    def __init__(self):
        AbstractProvidesNKeysForPartition.__init__(self)

    def generate_speed_up_data(self, vertex, routing_info):
        """ generates data needed for the speed up functionality to work
        :param routing_info: the routing infos containing the key needed
        :param vertex: the machine vertex to map to
        :return: data in a iterable array for sdram storage
        """
        local_routing_info = routing_info.get_routing_info_from_pre_vertex(
            vertex, constants.PARTITION_ID_FOR_MULTICAST_DATA_SPEED_UP)
        first_key = local_routing_info.first_key
        return [first_key]

    @overrides(AbstractProvidesNKeysForPartition.get_n_keys_for_partition)
    def get_n_keys_for_partition(self, partition, graph_mapper):
        if partition.identifier == \
                constants.PARTITION_ID_FOR_MULTICAST_DATA_SPEED_UP:
            return 3
        else:
            return None
