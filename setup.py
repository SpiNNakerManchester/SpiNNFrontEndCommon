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

import os
from collections import defaultdict
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

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
    classifiers=[
        "Development Status :: 5 - Production/Stable",

        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",

        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",

        "Natural Language :: English",

        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",

        "Programming Language :: C",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    packages=packages,
    package_data=package_data,
    install_requires=['SpiNNUtilities == 1!6.0.0',
                      'SpiNNMachine == 1!6.0.0',
                      'SpiNNMan == 1!6.0.0',
                      'SpiNNaker_PACMAN == 1!6.0.0',
                      'SpiNNaker_DataSpecification == 1!6.0.0',
                      'spalloc == 1!6.0.0',
                      'requests >= 2.4.1',
                      "numpy > 1.13, < 1.20; python_version == '3.6'",
                      "numpy > 1.13, < 1.21; python_version == '3.7'",
                      "numpy; python_version >= '3.8'",
                      "scipy >= 0.16.0, < 1.6; python_version == '3.6'",
                      "scipy >= 0.16.0; python_version >= '3.7'"],
    extras_require={
        'plotting': [
            'matplotlib',
            'seaborn',
        ]},
    entry_points={
        "console_scripts": [
            "spinnaker_router_provenance_mapper="
            "spinn_front_end_common.interface.provenance.router_prov_mapper:"
            "main [plotting]",
        ]},
    maintainer="SpiNNakerTeam",
    maintainer_email="spinnakerusers@googlegroups.com"
)
