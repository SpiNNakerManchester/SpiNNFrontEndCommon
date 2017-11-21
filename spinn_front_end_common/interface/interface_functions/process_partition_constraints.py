from spinn_front_end_common.utilities.exceptions import ConfigurationException


class processPartitionConstraints(object):

    def __call__(self, machine_graph=None, application_graph=None,
                 graph_mapper=None):
        if machine_graph is None:
            raise ConfigurationException(
                "A machine graph is required for this mapper. "
                "Please choose and try again")
        if (application_graph is None) != (graph_mapper is None):
            raise ConfigurationException(
                "Can only do one graph. semantically doing 2 graphs makes no "
                "sense. Please choose and try again")

        if application_graph is not None: