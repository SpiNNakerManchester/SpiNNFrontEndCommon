# Copyright (c) 2015 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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

        "License :: OSI Approved :: Apache License 2.0",

        "Natural Language :: English",

        "Operating System :: POSIX :: Linux",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",

        "Programming Language :: C",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    packages=packages,
    package_data=package_data,
    install_requires=['SpiNNUtilities == 1!6.0.1',
                      'SpiNNMachine == 1!6.0.1',
                      'SpiNNMan == 1!6.0.1',
                      'SpiNNaker_PACMAN == 1!6.0.1',
                      'SpiNNaker_DataSpecification == 1!6.0.1',
                      'spalloc == 1!6.0.1',
                      "scipy >= 0.16.0, < 1.8; python_version == '3.7'",
                      "scipy >= 0.16.0; python_version >= '3.8'"],
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
