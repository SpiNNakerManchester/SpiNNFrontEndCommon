from six import add_metaclass
from abc import ABCMeta
from abc import abstractmethod


@add_metaclass(ABCMeta)
class AbstractGeneratesDataSpecification(object):

    @abstractmethod
    def generate_data_specification(self, spec, placement):
        """ Generate a data specification

        :param spec: The data specification to write to
        :param placement: the placement object this spec is associated with
        :type spec:\
            :py:class:`data_specification.data_specification_generator.DataSpecificationGenerator`
        :return: None
        """
