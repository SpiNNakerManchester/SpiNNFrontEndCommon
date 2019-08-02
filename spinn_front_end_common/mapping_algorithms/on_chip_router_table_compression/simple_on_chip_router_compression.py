from .abstract_compression import AbstractCompression

_BINARY_NAME = "simple_minimise.aplx"


class SimpleOnChipRouterCompression(AbstractCompression):
    """ Compressor that uses a on chip router compressor
    """

    def __call__(
            self, routing_tables, transceiver, executable_finder,
            machine, app_id, provenance_file_path,
            compress_only_when_needed=False,
            compress_as_much_as_possible=True):
        """
        :param routing_tables: the memory routing tables to be compressed
        :param transceiver: the spinnman interface
        :param executable_finder:
        :param machine: the SpiNNaker machine representation
        :param app_id: the application ID used by the main application
        :param provenance_file_path: the path to where to write the data
        :return: flag stating routing compression and loading has been done
        """
        # pylint: disable=too-many-arguments
        # load the router compressor executable
        binary_path = executable_finder.get_executable_path(_BINARY_NAME)
        self._compress(routing_tables, transceiver,
                       machine, app_id, provenance_file_path, binary_path,
                       compress_only_when_needed, compress_as_much_as_possible)
