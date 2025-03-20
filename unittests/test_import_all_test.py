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

import os
import unittest
import spinn_utilities.package_loader as package_loader
from spinn_front_end_common.interface.config_setup import unittest_setup


class TestImportAllModule(unittest.TestCase):

    def setUp(self) -> None:
        unittest_setup()

    def test_import_all(self) -> None:
        if os.environ.get('CONTINUOUS_INTEGRATION', 'false').lower() == 'true':
            package_loader.load_module(
                "spinn_front_end_common", remove_pyc_files=False)
        else:
            package_loader.load_module(
                "spinn_front_end_common", remove_pyc_files=True)


if __name__ == "__main__":
    unittest.main()
