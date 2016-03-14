import pickle
import os


class ReloadRoutingTable(object):
    """ A routing table to be reloaded
    """

    @staticmethod
    def reload(routing_table_file_name):
        """ Reload a routing table via a pickled filename
        :param routing_table_file_name: the file name for the pickled routeing\
                    table
        :return: None
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
        :return:
        """
        pickle_file_name = "picked_routing_table_for_{}_{}".format(
            routing_table.x, routing_table.y)
        pickle_file_path = os.path.join(binary_directory, pickle_file_name)
        pickle_file = open(pickle_file_path, "wb")
        pickle.dump(routing_table, pickle_file)
        pickle_file.close()
        return pickle_file_name
