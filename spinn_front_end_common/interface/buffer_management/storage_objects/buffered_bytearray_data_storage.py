from spinn_front_end_common.interface.buffer_management.buffer_models.\
    abstract_buffered_data_storage import AbstractBufferedDataStorage


class BufferedBytearrayDataStorage(AbstractBufferedDataStorage):
    def __init__(self):
        self._data_storage = bytearray()
        self._read_pointer = 0
        self._write_pointer = 0

    def write(self, data):
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
        start_id = self._read_pointer
        end_id = start_id + data_size
        self._read_pointer = end_id
        data = self._data_storage[start_id:end_id]
        return data

    def read_all(self):
        return self._data_storage

    def seek_read(self, offset, whence=0):
        if whence == 0:
            self._read_pointer = offset
        elif whence == 1:
            self._read_pointer += offset
        elif whence == 2:
            self._read_pointer = len(self._data_storage) - abs(offset)

    def seek_write(self, offset, whence=0):
        if whence == 0:
            self._write_pointer = offset
        elif whence == 1:
            self._write_pointer += offset
        elif whence == 2:
            self._write_pointer = len(self._data_storage) - abs(offset)

    def tell_read(self):
        return self._read_pointer

    def tell_write(self):
        return self._write_pointer

    def eof(self):
        return len(self._data_storage) - self._read_pointer
