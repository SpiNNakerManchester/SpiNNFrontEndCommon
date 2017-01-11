from six import add_metaclass
from abc import ABCMeta
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractRewriteingDataRegions(object):
    @abstractmethod
    def regions_and_data_spec_to_rewrite(self):
        """ method for getting regions that need to be rewritten between runs
        :return: a dict of data regions and
        """
