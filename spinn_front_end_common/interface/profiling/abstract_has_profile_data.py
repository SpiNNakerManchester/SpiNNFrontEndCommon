from six import add_metaclass
from abc import ABCMeta
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractHasProfileData(object):
    """ Indicates an object that can record a profile
    """

    @abstractmethod
    def get_profile_data(self, transceiver, placements, graph_mapper):
        """ Get the profile data recorded during simulation

        :rtype:\
            :py:class:`spinn_front_end_common.interface.profiling.profile_data.ProfileData`
        """
