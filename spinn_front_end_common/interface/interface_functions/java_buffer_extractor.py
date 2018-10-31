import subprocess

from spinn_front_end_common.interface.buffer_management.buffer_models \
    import AbstractReceiveBuffersToHost
from spinn_utilities.progress_bar import ProgressBar


class JavaBufferExtractor(object):
    """ Extracts data in between runs
    """

    __slots__ = []

    def __call__(self, json_machine, json_placements, database_file):

        # Read back the regions
        progress = ProgressBar(1, "JavaBufferExtractor")
        try:
            subprocess.call(['java', '-jar', '/home/brenninc/spinnaker/JavaSpiNNaker/SpiNNaker-front-end/target/spinnaker-exe.jar',
                             'upload', json_placements, json_machine, database_file])
        finally:
            progress.end()
