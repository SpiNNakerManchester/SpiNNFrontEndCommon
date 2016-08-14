from six import add_metaclass
from abc import ABCMeta
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractUsesSimulation(object):

    __slots__ = []

    def __init__(self):
        pass

    @abstractmethod
    def data_for_simulation_data(self):
        pass
