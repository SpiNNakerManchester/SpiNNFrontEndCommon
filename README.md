[![Python Build Status](https://github.com/SpiNNakerManchester/SpiNNFrontEndCommon/workflows/Python%20Actions/badge.svg?branch=master)](https://github.com/SpiNNakerManchester/SpiNNFrontEndCommon/actions?query=workflow%3A%22Python+Actions%22+branch%3Amaster)
[![C Build Status](https://github.com/SpiNNakerManchester/SpiNNFrontEndCommon/workflows/C%20Actions/badge.svg?branch=master)](https://github.com/SpiNNakerManchester/SpiNNFrontEndCommon/actions?query=workflow%3A%22C+Actions%22+branch%3Amaster)
[![Documentation Status](https://readthedocs.org/projects/spinnfrontendcommon/badge/?version=latest)](https://spinnfrontendcommon.readthedocs.io/en/latest/?badge=latest)
[![Coverage Status](https://coveralls.io/repos/github/SpiNNakerManchester/SpiNNFrontEndCommon/badge.svg?branch=master)](https://coveralls.io/github/SpiNNakerManchester/SpiNNFrontEndCommon?branch=master)

This package provides functionality which are common to front ends that
translate application level programs into executables which run on a SpiNNaker
machine.

Requirements
============

In addition to a standard Python installation, this package depends on:

    numpy
    SpiNNUtilities
    SpiNNMachine
    DataSpecification
    PACMAN
    SpiNNMan
    spalloc

These dependencies can be installed using `pip`:

    pip install numpy
    pip install SpiNNUtilities SpiNNMachine DataSpecification PACMAN SpiNNMan spalloc

If you want to use the `spinnaker_router_provenance_mapper` command line tool
to visualise the traffic on SpiNNaker boards caused by your simulations, you
should install this package using:

    pip install "SpiNNFrontEndCommon[plotting]"

This will additionally install `matplotlib` and `seaborn` to do the actual
plotting, as well as configuring the script.

Visualising SpiNNaker Board Network Traffic
===========================================

To get plots of the traffic in your simulation, use the
`spinnaker_router_provenance_mapper` command line tool (installed as described
above), passing in the name of a provenance database (usually called
`provenance.sqlite3` and created within the run's reporting folders) that
contains the raw data. This will produce a number of graphs as images in your
current directory; _those have fixed file-names._

    spinnaker_router_provenance_mapper my_code/.../provenance.sqlite3

An example of the sort of map that might be produced is:

![External_P2P_Packets](.images/External_P2P_Packets.png)

The P2P traffic being mapped is mainly used for system boot and control.
The white square is due to a chip on that SpiNNaker board being marked as
deactivated.

Installing NumPy on Older Systems
=================================
_Note that this part is not normally required on newer systems,_
where `numpy` installs inside a virtual environment just fine.
Sometimes you have to provide a little assistance with:

    pip install --upgrade wheel
    pip install --binary-only numpy

Otherwise, use these instructions, depending on what platform you are using:

Ubuntu Linux
------------
Execute the following to install `numpy`:

    sudo apt-get install python-numpy

Fedora Linux
------------
Execute the following to install `numpy`:

    sudo yum install numpy

Windows 7/8 64-bit
------------------
Download and install http://spinnaker.cs.manchester.ac.uk/.../numpy-MKL-1.8.1.win-amd64-py2.7.exe

Windows 7/8 32-bit
------------------
Download and install http://spinnaker.cs.manchester.ac.uk/.../numpy-MKL-1.8.1.win32-py2.7.exe

Documentation
=============
[SpiNNFrontEndCommon Python documentation](http://spinnakermanchester.github.io/SpiNNFrontEndCommon/python/)
<br>
[SpiNNFrontEndCommon C documentation](http://spinnakermanchester.github.io/SpiNNFrontEndCommon/c/)

[Combined PyNN8 python documentation](http://spinnaker8manchester.readthedocs.io)
