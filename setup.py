from setuptools import setup
from collections import defaultdict
import os

__version__ = None
exec(open("spinn_front_end_common/_version.py").read())
assert __version__

# Build a list of all project modules, as well as supplementary files
main_package = "spinn_front_end_common"
extensions = {".aplx", ".boot", ".cfg", ".json", ".sql", ".template", ".xml",
              ".xsd"}
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
        if ext in extensions:
            package = "{}{}".format(
                main_package, dirname[start:].replace(os.sep, '.'))
            package_data[package].append(filename)

setup(
    name="SpiNNFrontEndCommon",
    version=__version__,
    description="Common Spinnaker Front end functions",
    url="https://github.com/SpiNNakerManchester/SpiNNFrontEndCommon",
    packages=packages,
    package_data=package_data,
    install_requires=['SpiNNUtilities >= 1!4.0.0, < 1!5.0.0',
                      'SpiNNStorageHandlers >= 1!4.0.0, < 1!5.0.0',
                      'SpiNNMachine >= 1!4.0.0, < 1!5.0.0',
                      'SpiNNMan >= 1!4.0.0, < 1!5.0.0',
                      'SpiNNaker_PACMAN >= 1!4.0.0, < 1!5.0.0',
                      'SpiNNaker_DataSpecification >= 1!4.0.0, < 1!5.0.0',
                      'spalloc >= 1.0.0, < 2.0.0',
                      'requests >= 2.4.1',
                      'scipy >= 0.16.0',
                      'numpy',
                      'six']
)
