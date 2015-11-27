import tempfile
import os

from spinn_front_end_common.interface.buffer_management.buffer_models.\
    abstract_buffered_data_storage import AbstractBufferedDataStorage


class BufferedFileDataStorage(AbstractBufferedDataStorage):
    """ Data storage based on a temporary file with two pointers, one for\
        reading and one for writing
    """

    def __init__(self):
        self._file = tempfile.TemporaryFile()
        self._file_size = 0
        self._read_pointer = 0
        self._write_pointer = 0

    def write(self, data):
        if not isinstance(data, bytearray):
            raise
        self._file.seek(self._write_pointer)
        self._file.write(data)
        self._file_size += len(data)
        self._write_pointer += len(data)

    def read(self, data_size):
        self._file.seek(self._read_pointer)
        data = self._file.read(data_size)
        self._read_pointer += data_size
        return data

    def read_all(self):
        self._file.seek(0)
        data = self._file.read()
        self._read_pointer = self._file.tell()
        return data

    def seek_read(self, offset, whence=os.SEEK_SET):
        if whence == os.SEEK_SET:
            self._read_pointer = offset
        elif whence == os.SEEK_CUR:
            self._read_pointer += offset
        elif whence == os.SEEK_END:
            self._read_pointer = self._file_size - abs(offset)

        if self._read_pointer < 0:
            self._read_pointer = 0

        file_len = self._file_len
        if self._read_pointer > file_len:
            self._read_pointer = file_len

    def seek_write(self, offset, whence=os.SEEK_SET):
        if whence == os.SEEK_SET:
            self._write_pointer = offset
        elif whence == os.SEEK_CUR:
            self._write_pointer += offset
        elif whence == os.SEEK_END:
            self._write_pointer = self._file_size - abs(offset)

        if self._write_pointer < 0:
            self._write_pointer = 0

        file_len = self._file_len
        if self._write_pointer > file_len:
            self._write_pointer = file_len

    def tell_read(self):
        return self._read_pointer

    def tell_write(self):
        return self._write_pointer

    def eof(self):
        file_len = self._file_len
        return (file_len - self._read_pointer) <= 0

    @property
    def _file_len(self):
        """ The size of the file

        :return: The size of the file
        :rtype: int
        """
        current_pos = self._file.tell()
        self._file.seek(0, 2)
        end_pos = self._file.tell()
        self._file.seek(current_pos)
        return end_pos
