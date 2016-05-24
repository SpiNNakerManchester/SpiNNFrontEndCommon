from six import add_metaclass
from abc import ABCMeta
from abc import abstractmethod
from abc import abstractproperty


@add_metaclass(ABCMeta)
class AbstractChangableAfterRun(object):
    """ An item that can be changed after a call to run, the changes to which\
        might or might not require mapping
    """

    @abstractmethod
    def requires_remapping_for_change(self, parameter, old_value, new_value):
        """
        states if the vertex needs remapping given the given parameter is being
        change from old value to new value
        :param new_value:
        :param old_value:
        :param parameter:
        :return:
        """


    @abstractproperty
    def requires_mapping(self):
        """ True if changes that have been made require that mapping be\
            performed.  Note that this should return True the first time it\
            is called, as the vertex must require mapping as it has been\
            created!
        """

    @abstractmethod
    def mark_no_changes(self):
        """ Marks the point after which changes are reported.  Immediately\
            after calling this method, requires_mapping should return False.
        """
