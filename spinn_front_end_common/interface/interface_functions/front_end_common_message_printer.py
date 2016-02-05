import logging
import os
logger = logging.getLogger(__name__)


class FrontEndCommonMessagePrinter(object):
    """
    FrontEndCommonMessagePrinter: interface for printing errors and warning to
    end user
    """

    def __call__(self, error_messages, warn_messages, io_buffers, prov_path):
        # print out error states
        if len(error_messages.get_cores_with_messages()) != 0:
            logger.error("Errors stated from the executed code are:")
            for (x, y, p) in error_messages.get_cores_with_messages():
                for message in error_messages.get_core_messages(x, y, p):
                    logger.error("{}:{}:{}:{}:{}".format(
                        x, y, p,message['message'], message['trace']))

        # print out warning states from cores
        if len(warn_messages.get_cores_with_messages()) != 0:
            logger.warn("Warnings stated from the executed code are: ")
            for (x, y, p) in warn_messages.get_cores_with_messages():
                for message in warn_messages.get_core_messages(x, y, p):
                    logger.warn("{}:{}:{}:{}:{}".format(
                        x, y, p, message['message'], message['trace']))

        # print out warning states from chips
        if len(warn_messages.get_chips_with_messages()) != 0:
            logger.warn("Warnings stated from the SpiNNaker chips are: ")
            for (x, y) in warn_messages.get_chips_with_messages():
                for message in warn_messages.get_core_messages(x, y):
                    logger.warn("{}:{}:{}:{}".format(x, y, message['message']))

        for iobuf in io_buffers:
            file_path = os.path.join(
                prov_path,
                "IO_buffer_for[{}:{}:{}]".format(iobuf.x, iobuf.y, iobuf.p))
            output = open(file_path, mode="w")
            output.writelines(iobuf.iobuf)
            output.flush()
            output.close()
