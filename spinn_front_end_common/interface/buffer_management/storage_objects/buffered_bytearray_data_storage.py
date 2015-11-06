from spinn_front_end_common.interface.buffer_management.buffer_models.\
    abstract_buffered_data_storage import AbstractBufferedDataStorage


class BufferedBytearrayDataStorage(AbstractBufferedDataStorage):
    """
    Data storage based on a bytearray buffer with two pointers, one for reading
    and one for writing
    """

    def __init__(self):
        """

        :return: None
        :rtype: None
        """
        self._data_storage = bytearray()
        self._read_pointer = 0
        self._write_pointer = 0

    def write(self, data):
        """
        Stores data in the bytearray buffer in the position indicated by the
        write pointer index

        :param data: the data to be stored
        :type data: bytearray
        :return: None
        :rtype: None
        """
        if not isinstance(data, bytearray):
            raise
        if len(self._data_storage) == self._write_pointer:
            self._data_storage.extend(data)
        else:
            temp1 = self._data_storage[0:self._write_pointer]
            temp2 = self._data_storage[self._write_pointer:]
            temp1.extend(data)
            temp1.extend(temp2)
            self._data_storage = temp1
        self._write_pointer = len(self._data_storage)

    def read(self, data_size):
        """
        Read data from the bytearray buffer from the position indicated by the
        read pointer index

        :param data_size: number of bytes to be read
        :type data_size: int
        :return: a bytearray containing the data read
        :rtype: bytearray
        """
        start_id = self._read_pointer
        end_id = start_id + data_size
        self._read_pointer = end_id
        data = self._data_storage[start_id:end_id]
        return data

    def read_all(self):
        """
        Reads all the data contained in the bytearray buffer starting from
        position 0 to the end

        :return: a bytearray containing the data read
        :rtype: bytearray
        """
        return self._data_storage

    def seek_read(self, offset, whence=0):
        """
        Sets the buffer's current read position at the offset.
        The whence argument is optional and defaults to 0, which means
        absolute buffer positioning, other values are 1 which means seek
        relative to the current position and 2 means seek relative to
        the buffer's end.

        :param offset: Position of the read pointer within the buffer
        :type offset: int
        :param whence: This is optional and defaults to 0 which
        means absolute buffer positioning, other values are 1 which
        means seek relative to the current read position and 2 means seek
        relative to the buffer's end.
        :return: None
        :rtype: None
        """
        if whence == 0:
            self._read_pointer = offset
        elif whence == 1:
            self._read_pointer += offset
        elif whence == 2:
            self._read_pointer = len(self._data_storage) - abs(offset)

        if self._read_pointer < 0:
            self._read_pointer = 0

        if self._read_pointer > len(self._data_storage):
            self._read_pointer = len(self._data_storage)

    def seek_write(self, offset, whence=0):
        """
        Sets the buffer's current write position at the offset.
        The whence argument is optional and defaults to 0, which means
        absolute buffer positioning, other values are 1 which means seek
        relative to the current position and 2 means seek relative to
        the buffer's end.

        :param offset: Position of the write pointer within the buffer
        :type offset: int
        :param whence: This is optional and defaults to 0 which
        means absolute buffer positioning, other values are 1 which
        means seek relative to the current read position and 2 means seek
        relative to the buffer's end.
        :return: None
        :rtype: None
        """
        if whence == 0:
            self._write_pointer = offset
        elif whence == 1:
            self._write_pointer += offset
        elif whence == 2:
            self._write_pointer = len(self._data_storage) - abs(offset)

        if self._write_pointer < 0:
            self._write_pointer = 0

        if self._write_pointer > len(self._data_storage):
            self._write_pointer = len(self._data_storage)

    def tell_read(self):
        """
        Returns the current position of the read pointer

        :return: The current position of the read pointer
        :rtype: int
        """
        return self._read_pointer

    def tell_write(self):
        """
        Returns the current position of the write pointer

        :return: The current position of the write pointer
        :rtype: int
        """
        return self._write_pointer

    def eof(self):
        """
        Checks if the read pointer is a the end of the buffer

        :return: 0 if the read pointer is at the end of the buffer
        :rtype: int
        """
        return len(self._data_storage) - self._read_pointer
