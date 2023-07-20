
This package provides functionality which are common to front ends that
translate application level programs into executables which run on a SpiNNaker
machine.

Requirements
============

In addition to a standard Python installation, this package depends on:

    numpy
    SpiNNUtilities
    SpiNNMachine
    PACMAN
    SpiNNMan
    spalloc

These dependencies can be installed using `pip`:

    pip install numpy
    pip install SpiNNUtilities SpiNNMachine PACMAN SpiNNMan spalloc

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

Documentation
=============
[SpiNNFrontEndCommon python documentation](https://spinnfrontendcommon.readthedocs.io/en/7.0.0)
<br>
[SpiNNFrontEndCommon C documentation](http://spinnakermanchester.github.io/SpiNNFrontEndCommon/c/)

[Combined python documentation](http://spinnakermanchester.readthedocs.io/en/7.0.0)


Pip Freeze
==========
This code was tested with all (SpiNNakerManchester)[https://github.com/SpiNNakerManchester] on tag 7.0.0

Pip Freeze showed the dependencies as:

appdirs==1.4.4

astroid==2.15.6

attrs==23.1.0

certifi==2023.5.7

charset-normalizer==3.2.0

contourpy==1.1.0

coverage==7.2.7

csa==0.1.12

cycler==0.11.0

dill==0.3.6

ebrains-drive==0.5.1

exceptiongroup==1.1.2

execnet==2.0.2

fonttools==4.41.0

graphviz==0.20.1

httpretty==1.1.4

idna==3.4

importlib-resources==6.0.0

iniconfig==2.0.0

isort==5.12.0

jsonschema==4.18.4

jsonschema-specifications==2023.7.1

kiwisolver==1.4.4

lazy-object-proxy==1.9.0

lazyarray==0.5.2

matplotlib==3.7.2

mccabe==0.7.0

mock==5.1.0

multiprocess==0.70.14

neo==0.12.0

numpy==1.24.4

opencv-python==4.8.0.74

packaging==23.1

pathos==0.3.0

Pillow==10.0.0

pkgutil_resolve_name==1.3.10

platformdirs==3.9.1

pluggy==1.2.0

pox==0.3.2

ppft==1.7.6.6

py==1.11.0

pylint==2.17.4

PyNN==0.11.0

pyparsing==2.4.7

pytest==7.4.0

pytest-cov==4.1.0

pytest-forked==1.6.0

pytest-instafail==0.5.0

pytest-progress==1.2.5

pytest-timeout==2.1.0

pytest-xdist==3.3.1

python-coveralls==2.9.3

python-dateutil==2.8.2

PyYAML==6.0.1

quantities==0.14.1

referencing==0.30.0

requests==2.31.0

rpds-py==0.9.2

scipy==1.10.1

six==1.16.0

tomli==2.0.1

tomlkit==0.11.8

typing_extensions==4.7.1

urllib3==2.0.4

websocket-client==1.6.1

wrapt==1.15.0

zipp==3.16.2

