from abc import ABCMeta
from abc import abstractmethod
from six import add_metaclass


@add_metaclass(ABCMeta)
class AbstractResetableForRunInterface(object):
    """
    ResetableForRun: interface to support
    """

    @abstractmethod
    def reset_for_run(self, last_runtime_in_milliseconds,
                      this_runtime_in_milliseconds):
        """
        supports models that need to be reset between runs
        :param last_runtime_in_milliseconds:
        the last length of time in milliseconds ran in previous runs
        :param this_runtime_in_milliseconds: the length of time in
        milliseconds for this run
        :return: None
        """
