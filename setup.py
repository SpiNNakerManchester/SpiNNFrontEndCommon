# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from setuptools import setup
try:
    from collections.abc import defaultdict
except ImportError:
    from collections import defaultdict
import os

__version__ = None
exec(open("spinn_front_end_common/_version.py").read())
assert __version__

# Build a list of all project modules, as well as supplementary files
main_package = "spinn_front_end_common"
extensions = {".aplx", ".boot", ".cfg", ".json", ".sql", ".template", ".xml",
              ".xsd", ".dict"}
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
    description="Common SpiNNaker Front end functions",
    url="https://github.com/SpiNNakerManchester/SpiNNFrontEndCommon",
    packages=packages,
    package_data=package_data,
    install_requires=['SpiNNUtilities >= 1!5.0.0, < 1!6.0.0',
                      'SpiNNStorageHandlers >= 1!5.0.0, < 1!6.0.0',
                      'SpiNNMachine >= 1!5.0.0, < 1!6.0.0',
                      'SpiNNMan >= 1!5.0.0, < 1!6.0.0',
                      'SpiNNaker_PACMAN >= 1!5.0.0, < 1!6.0.0',
                      'SpiNNaker_DataSpecification >= 1!5.0.0, < 1!6.0.0',
                      'spalloc >= 2.0.0, < 3.0.0',
                      'requests >= 2.4.1',
                      'scipy >= 0.16.0',
                      'numpy',
                      'futures; python_version == "2.7"',
                      'six'],
    maintainer="SpiNNakerTeam",
    maintainer_email="spinnakerusers@googlegroups.com"
)
