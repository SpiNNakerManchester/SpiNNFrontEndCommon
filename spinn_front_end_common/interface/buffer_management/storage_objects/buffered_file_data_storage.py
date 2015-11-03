import tempfile

from spinn_front_end_common.interface.buffer_management.buffer_models.\
    abstract_buffered_data_storage import AbstractBufferedDataStorage


class BufferedFileDataStorage(AbstractBufferedDataStorage):
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

    def seek_read(self, offset, whence=0):
        if whence == 0:
            self._read_pointer = offset
        elif whence == 1:
            self._read_pointer += offset
        elif whence == 2:
            self._read_pointer = self._file_size - abs(offset)

    def seek_write(self, offset, whence=0):
        if whence == 0:
            self._write_pointer = offset
        elif whence == 1:
            self._write_pointer += offset
        elif whence == 2:
            self._write_pointer = self._file_size - abs(offset)

    def tell_read(self):
        return self._read_pointer

    def tell_write(self):
        return self._write_pointer

    def eof(self):
        self._file.seek(0, 2)
        file_len = self._file.tell()
        self._file.seek(self._read_pointer)
        return file_len - self._read_pointer
