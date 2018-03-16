[![Build Status](https://travis-ci.org/SpiNNakerManchester/SpiNNFrontEndCommon.svg?branch=master)](https://travis-ci.org/SpiNNakerManchester/SpiNNFrontEndCommon)
[![Coverage Status](https://coveralls.io/repos/github/SpiNNakerManchester/SpiNNFrontEndCommon/badge.svg?branch=master)](https://coveralls.io/github/SpiNNakerManchester/SpiNNFrontEndCommon?branch=master)

This package provides functionality which are common to front ends that
translate application level programs into executables which run on a SpiNNaker
machine.

Requirements
============

In addition to a standard Python installation, this package depends on:

    six
    enum34
    SpiNNStorageHandlers
    DataSpecification
    PACMAN
    SpiNNMan
    SpiNNMachine
    PyNN
    numpy

These dependencies, excluding `numpy`, can be installed using `pip`:

    pip install six
    pip install enum34
    pip install SpiNNStorageHandlers
    pip install DataSpecification
    pip install PACMAN
    pip install SpiNNMan
    pip install PyNN
    pip install SpiNNFrontEndCommon
    pip install SpiNNMachine

Details of the installation of `numpy` on various operating systems are shown
below.

Installing NumPy
================
If you are using `virtualenv`, please also follow the instructions below to
install `numpy`. Further instructions for adding this global package to your
`virutalenv` are detailed in the "_User Installation_" and
"_Developer Installation_" sections below.

Ubuntu Linux
------------
Execute the following to install both `gtk` and `pygtk`:

    sudo apt-get install python-numpy

Fedora Linux
------------
Execute the following to install both `gtk` and `pygtk`:

    sudo yum install numpy

Windows 7/8 64-bit
------------------
Download and install http://spinnaker.cs.manchester.ac.uk/.../numpy-MKL-1.8.1.win-amd64-py2.7.exe

Windows 7/8 32-bit
------------------
Download and install http://spinnaker.cs.manchester.ac.uk/.../numpy-MKL-1.8.1.win32-py2.7.exe

Documentation
=============
[SpiNNFrontEndCommon Python documentation](http://spinnakergraphfrontend.readthedocs.io)

[Combined PyNN7 python documentation](http://spinnaker7manchester.readthedocs.io)

[Combined PyNN8 python documentation](http://spinnaker8manchester.readthedocs.io)
