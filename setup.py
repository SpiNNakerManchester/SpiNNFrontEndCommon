from setuptools import setup

setup(
    name="SpiNNFrontEndCommon",
    version="2016.001",
    description="Common Spinnaker Front end functions",
    url="https://github.com/SpiNNakerManchester/SpiNNFrontEndCommon",
    packages=[
        'spinn_front_end_common',
        'spinn_front_end_common.abstract_models',
        'spinn_front_end_common.common_model_binaries',
        'spinn_front_end_common.interface',
        'spinn_front_end_common.interface.buffer_management',
        'spinn_front_end_common.interface.buffer_management.buffer_models',
        'spinn_front_end_common.interface.buffer_management.storage_objects',
        'spinn_front_end_common.interface.interface_functions',
        'spinn_front_end_common.interface.provenance',
        'spinn_front_end_common.utilities',
        'spinn_front_end_common.utilities.connections',
        'spinn_front_end_common.utilities.database',
        'spinn_front_end_common.utilities.notification_protocol',
        'spinn_front_end_common.utilities.reload',
        'spinn_front_end_common.utilities.report_functions',
        'spinn_front_end_common.utilities.scp',
        'spinn_front_end_common.utilities.utility_objs',
        'spinn_front_end_common.utility_models'],
    package_data={
        'spinn_front_end_common.common_model_binaries': ['*.aplx'],
        'spinn_front_end_common.interface.interface_functions': ['*.xml'],
        'spinn_front_end_common.utilities.report_functions': ['*.xml']},
    install_requires=['SpiNNMachine == 2016.001',
                      'SpiNNMan == 2016.001',
                      'SpiNNaker_PACMAN == 2016.001',
                      'SpiNNaker_DataSpecification == 2016.001',
                      'SpiNNStorageHandlers == 2016.001',
                      'spalloc >= v0.2.2',
                      'requests >= 2.4.1',
                      'numpy', 'six']
)
