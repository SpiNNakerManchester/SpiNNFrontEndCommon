from six import add_metaclass
from abc import ABCMeta


@add_metaclass(ABCMeta)
class AbstractGeneratesDataSpecification(object):

    def generate_data_specification(self, spec):
        """ Generate a data specification

        :param spec: The data specification to write to
        :type spec:\
            :py:class:`data_specification.data_specification_generator.DataSpecificationGenerator`
        """
