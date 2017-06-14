from setuptools import setup
from collections import defaultdict
import os

# Build a list of all project modules, as well as supplementary files
main_package = "spinn_front_end_common"
data_extensions = {".aplx", ".xml"}
main_package_dir = os.path.join(os.path.dirname(__file__), main_package)
start = len(main_package_dir)
packages = []
package_data = defaultdict(list)
for dirname, dirnames, filenames in os.walk(main_package_dir):
    if '__init__.py' in filenames:
        package = "{}{}".format(
            main_package, dirname[start:].replace(os.sep, '.'))
        packages.append(package)
    for filename in filenames:
        _, ext = os.path.splitext(filename)
        if ext in data_extensions:
            package = "{}{}".format(
                main_package, dirname[start:].replace(os.sep, '.'))
            package_data[package].append("*{}".format(ext))
            break

setup(
    name="SpiNNFrontEndCommon",
    version="3.0.1",
    description="Common Spinnaker Front end functions",
    url="https://github.com/SpiNNakerManchester/SpiNNFrontEndCommon",
    packages=packages,
    package_data=package_data,
    install_requires=['SpiNNUtilities >= 3.0.0, < 4.0.0',
                      'SpiNNMachine >= 3.0.0, < 4.0.0',
                      'SpiNNMan >= 3.0.0, < 4.0.0',
                      'SpiNNaker_PACMAN >= 3.0.0, < 4.0.0',
                      'SpiNNaker_DataSpecification >= 3.0.0, < 4.0.0',
                      'SpiNNStorageHandlers >= 3.0.0, < 4.0.0',
                      'spalloc >= v0.2.2, < v1.0.0',
                      'requests >= 2.4.1',
                      'numpy', 'six']
)
