from six import add_metaclass
from spinn_utilities.abstract_base import AbstractBase, abstractmethod, \
    abstractproperty


@add_metaclass(AbstractBase)
class AbstractRequiresTDMA(object):
    """ Abstract interface for requesting a TDMA for it

    """

    __slots__ = []

    @abstractmethod
    def find_n_phases_for(self, app_vertex, machine_graph, n_keys_map):
        """

        :param app_vertex:
        :param machine_graph:
        :param n_keys_map:
        :return:
        """

    @abstractmethod
    def set_initial_offset(self, new_value):
        """ sets the initial offset

        :param new_value: the new initial offset
        :rtype: None
        """

    @abstractmethod
    def set_other_timings(
            self, time_between_cores, n_slots, time_between_spikes):
        """ sets the other timings needed for the TDMA

        :param time_between_cores: time between cores
        :param n_slots: the number of slots
        :param time_between_spikes: the time to wait between spikes
        :rtype: None
        """

    @abstractmethod
    def generate_tdma_data_specification_data(self, vertex_index):
        """ generates data needed for the data spec

        :param vertex_index: the machine vertex index in the pop
        :return: array of data to write.
        """

    @abstractproperty
    def tdma_sdram_size_in_bytes(self):
        """ returns the number of bytes needed by this interface

        :return: the number of bytes required by this interface
        """

    @abstractmethod
    def get_n_cores(self, app_vertex):
        """ returns the number of cores this app vertex is using in the TDMA

        :param app_vertex: the app vertex in question
        :return: the number of cores to use in the TDMA
        """




