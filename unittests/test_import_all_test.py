import os
import unittest
import spinn_utilities.package_loader as package_loader


class TestImportAllModule(unittest.TestCase):

    def test_import_all(self):
        if os.environ.get('CONTINUOUS_INTEGRATION', 'false').lower() == 'true':
            package_loader.load_module(
                "spinn_front_end_common", remove_pyc_files=False)
        else:
            package_loader.load_module(
                "spinn_front_end_common", remove_pyc_files=True)


if __name__ == "__main__":
    unittest.main()
