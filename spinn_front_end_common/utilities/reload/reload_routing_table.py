import pickle
import os


class ReloadRoutingTable(object):
    """ A routing table to be reloaded
    """

    @staticmethod
    def reload(routing_table_file_name):
        """ Reload a routing table via a pickled filename

        :param routing_table_file_name: the file name for the pickled routing\
                    table
        """
        routing_table_file = open(routing_table_file_name, "rb")
        routing_table = pickle.load(routing_table_file)
        routing_table_file.close()
        return routing_table

    @staticmethod
    def store(binary_directory, routing_table):
        """ Store a routing table in pickled form

        :param binary_directory:
        :param routing_table:
        """
        pickle_file_name = "picked_routing_table_for_{}_{}".format(
            routing_table.x, routing_table.y)
        pickle_file_path = os.path.join(binary_directory, pickle_file_name)
        pickle_file = open(pickle_file_path, "wb")

        # the protocol = -1 is used to allow pickle to pickle objects which
        # have __slots__ but don't have __getstate__
        # (as all of pacman objects do), as shown from link below
        # http://stackoverflow.com/questions/2204155/why-am-i-getting-an-error-about-my-class-defining-slots-when-trying-to-pickl

        pickle.dump(routing_table, pickle_file, protocol=-1)
        pickle_file.close()
        return pickle_file_name
