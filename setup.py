from setuptools import setup

setup(
    name="SpiNNFrontEndCommon",
    version="2015.001",
    description="Common Spinnaker Front end functions",
    url="https://github.com/SpiNNakerManchester/SpiNNFrontEndCommon",
    packages=['spinn_front_end_common',
              'spinn_front_end_common.abstract_models',
              'spinn_front_end_common.common_model_binaries',
              'spinn_front_end_common.interface',
              'spinn_front_end_common.utilities',
              'spinn_front_end_common.utility_models'],
    package_data={'spinn_front_end_common.common_model_binaries': ['*.aplx']},
    install_requires=['SpiNNMachine >= 2015.003',
                      'SpiNNMan >= 2015.003',
                      'SpiNNaker_PACMAN >= 2015.003',
                      'SpiNNaker_DataSpecification >= 2015.003',
                      'numpy', 'six']
)
