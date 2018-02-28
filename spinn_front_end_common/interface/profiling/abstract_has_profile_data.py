from six import add_metaclass
from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractHasProfileData(object):
    """ Indicates an object that can record a profile
    """
    __slots__ = ()

    @abstractmethod
    def get_profile_data(self, transceiver, placement):
        """ Get the profile data recorded during simulation

        :rtype:\
            :py:class:`spinn_front_end_common.interface.profiling.profile_data.ProfileData`
        """
