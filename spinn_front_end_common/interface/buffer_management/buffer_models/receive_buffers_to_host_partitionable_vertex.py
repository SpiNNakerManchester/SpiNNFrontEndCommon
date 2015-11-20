from abc import abstractmethod, ABCMeta
from six import add_metaclass
from pacman.model.constraints.placer_constraints.\
    placer_radial_placement_from_chip_constraint import \
    PlacerRadialPlacementFromChipConstraint
from pacman.model.constraints.tag_allocator_constraints.\
    tag_allocator_require_iptag_constraint import \
    TagAllocatorRequireIptagConstraint


@add_metaclass(ABCMeta)
class ReceiveBuffersToHostPartitionableVertex(object):
    """ This class stores the information required to activate the buffering \
        output functionality for a vertex
    """
    def __init__(
            self, buffering_ip_address, buffering_port,
            buffering_output=False):
        """

        :param buffering_ip_address: IP address of the host which supports\
                the buffering output functionality
        :type buffering_ip_address: string
        :param buffering_port: UDP port of the host which supports\
                the buffering output functionality
        :type buffering_port: int
        :param buffering_output: boolean indicating if the buffering output\
                functionality is activated
        :param buffering_output: bool
        :return: None
        :rtype: None
        """
        self._buffering_output = buffering_output
        self._buffering_ip_address = buffering_ip_address
        self._buffering_port = buffering_port
        self._buffer_manager = None

    @property
    def buffering_output(self):
        """ True if the output buffering mechanism is activated

        :return: Boolean indicating whether the output buffering mechanism\
                is activated
        :rtype: bool
        """
        return self._buffering_output

    def set_buffering_output(self):
        """ Activates the output buffering mechanism

        :return: None
        :rtype: None
        """
        if not self._buffering_output:
            self._buffering_output = True

            board_address = None
            notification_tag = None
            notification_strip_sdp = True

            self.add_constraint(
                TagAllocatorRequireIptagConstraint(
                    self._buffering_ip_address, self._buffering_port,
                    notification_strip_sdp, board_address, notification_tag))

            # add placement constraint
            placement_constraint = PlacerRadialPlacementFromChipConstraint(
                0, 0)
            self.add_constraint(placement_constraint)

    @abstractmethod
    def get_buffered_regions_list(self):
        pass

    @abstractmethod
    def add_constraint(self, constraint):
        pass

    @staticmethod
    def is_buffering_recordable():
        return True

    @property
    def buffer_manager(self):
        return self._buffer_manager

    @buffer_manager.setter
    def buffer_manager(self, buffer_manager):
        self._buffer_manager = buffer_manager
