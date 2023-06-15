# Copyright (c) 2017 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations
import io
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .ds_sqllite_database import DsSqlliteDatabase


class DataRowWriter(io.RawIOBase):
    __slots__ = (
        "_x",
        "_y",
        "_p",
        "_targets",
        "_data", )

    def __init__(self, x: int, y: int, p: int, targets: DsSqlliteDatabase):
        super().__init__()
        self._x = x
        self._y = y
        self._p = p
        self._targets = targets
        self._data = bytearray()

    def write(self, data: bytes):  # type: ignore[override]
        assert self.closed is False
        self._data += data

    def readable(self):
        return False

    def seekable(self):
        return False

    def writable(self):
        return False

    def truncate(self, size=None):
        # Ignore
        pass

    def fileno(self):
        raise OSError

    def close(self) -> None:
        """
        Closes the writer if not already closed.
        """
        if not self.closed:
            self._targets.write_data_spec(
                self._x, self._y, self._p, self._data)
        super().close()
