"""
ReloadApplicationData
"""

# general imports
import os


class ReloadApplicationData(object):
    """ Data to be reloaded
    """

    def __init__(self, data_file, chip_x, chip_y, processor_id, base_address):
        self._data_file = data_file
        self._chip_x = chip_x
        self._chip_y = chip_y
        self._processor_id = processor_id
        self._base_address = base_address
        self._data_size = os.stat(self._data_file).st_size

    @property
    def data_file(self):
        """
        property for the data file used in application data
        :return:
        """
        return self._data_file

    @property
    def chip_x(self):
        """
        property for getting the chip's x corrinate that this application
        data is associated with
        :return:
        """
        return self._chip_x

    @property
    def chip_y(self):
        """
        property for getting the chip's y corrinate that this application
        data is associated with
        :return:
        """
        return self._chip_y

    @property
    def processor_id(self):
        """
        property for getting the processors id that this application data is
        associted with
        :return:
        """
        return self._processor_id

    @property
    def base_address(self):
        """
        property for getting the base address of where this applciation data
        needs to be stored on the chips SDRAM
        :return:
        """
        return self._base_address

    @property
    def data_size(self):
        """
        property for getting how much SDRAM this application data needs when
        being loaded.
        :return:
        """
        return self._data_size
