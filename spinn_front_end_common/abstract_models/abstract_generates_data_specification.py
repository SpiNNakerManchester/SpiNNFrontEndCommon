from six import add_metaclass

from spinn_utilities.abstract_base import AbstractBase, abstractmethod


@add_metaclass(AbstractBase)
class AbstractGeneratesDataSpecification(object):

    __slots__ = ()

    @abstractmethod
    def generate_data_specification(self, spec, placement):
        """ Generate a data specification

        :param spec: The data specification to write to
        :param placement: the placement object this spec is associated with
        :type spec:\
            :py:class:`data_specification.data_specification_generator.DataSpecificationGenerator`
        :rtype: None
        """
