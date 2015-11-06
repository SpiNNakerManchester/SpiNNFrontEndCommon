import tempfile

from spinn_front_end_common.interface.buffer_management.buffer_models.\
    abstract_buffered_data_storage import AbstractBufferedDataStorage


class BufferedFileDataStorage(AbstractBufferedDataStorage):
    """
    Data storage based on a temporary file with two pointers, one for reading
    and one for writing
    """

    def __init__(self):
        """

        :return: None
        :rtype: None
        """
        self._file = tempfile.TemporaryFile()
        self._file_size = 0
        self._read_pointer = 0
        self._write_pointer = 0

    def write(self, data):
        """
        Stores data in the temporary file in the position indicated by the
        write pointer index

        :param data: the data to be stored
        :type data: bytearray
        :return: None
        :rtype: None
        """
        if not isinstance(data, bytearray):
            raise
        self._file.seek(self._write_pointer)
        self._file.write(data)
        self._file_size += len(data)
        self._write_pointer += len(data)

    def read(self, data_size):
        """
        Read data from the temporary file from the position indicated by the
        read pointer index

        :param data_size: number of bytes to be read
        :type data_size: int
        :return: a bytearray containing the data read
        :rtype: bytearray
        """
        self._file.seek(self._read_pointer)
        data = self._file.read(data_size)
        self._read_pointer += data_size
        return data

    def read_all(self):
        """
        Reads all the data contained in the temporary file starting from
        position 0 to the end

        :return: a bytearray containing the data read
        :rtype: bytearray
        """
        self._file.seek(0)
        data = self._file.read()
        self._read_pointer = self._file.tell()
        return data

    def seek_read(self, offset, whence=0):
        """
        Sets the file's current read position at the offset.
        The whence argument is optional and defaults to 0, which means
        absolute file positioning, other values are 1 which means seek
        relative to the current position and 2 means seek relative to
        the file's end.

        :param offset: Position of the read pointer within the file
        :type offset: int
        :param whence: This is optional and defaults to 0 which
        means absolute file positioning, other values are 1 which
        means seek relative to the current read position and 2 means seek
        relative to the file's end.
        :return: None
        :rtype: None
        """
        if whence == 0:
            self._read_pointer = offset
        elif whence == 1:
            self._read_pointer += offset
        elif whence == 2:
            self._read_pointer = self._file_size - abs(offset)

        if self._read_pointer < 0:
            self._read_pointer = 0

        file_len = self._file_len
        if self._read_pointer > file_len:
            self._read_pointer = file_len

    def seek_write(self, offset, whence=0):
        """
        Sets the file's current write position at the offset.
        The whence argument is optional and defaults to 0, which means
        absolute file positioning, other values are 1 which means seek
        relative to the current position and 2 means seek relative to
        the file's end.

        :param offset: Position of the write pointer within the file
        :type offset: int
        :param whence: This is optional and defaults to 0 which
        means absolute file positioning, other values are 1 which
        means seek relative to the current read position and 2 means seek
        relative to the file's end.
        :return: None
        :rtype: None
        """
        if whence == 0:
            self._write_pointer = offset
        elif whence == 1:
            self._write_pointer += offset
        elif whence == 2:
            self._write_pointer = self._file_size - abs(offset)

        if self._write_pointer < 0:
            self._write_pointer = 0

        file_len = self._file_len
        if self._write_pointer > file_len:
            self._write_pointer = file_len

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
        Checks if the read pointer is a the end of the file

        :return: 0 if the read pointer is at the end of the file
        :rtype: int
        """
        file_len = self._file_len
        return file_len - self._read_pointer

    @property
    def _file_len(self):
        """
        Returns the size of the file

        :return: The size of the file
        :rtype: int
        """
        current_pos = self._file.tell()
        self._file.seek(0, 2)
        end_pos = self._file.tell()
        self._file.seek(current_pos)
        return end_pos
