from spinn_front_end_common.utilities import helpful_functions
from spinn_front_end_common.utilities import constants
from spinn_front_end_common.utilities import exceptions

from spinnman.messages.scp.scp_signal import SCPSignal
from spinnman.messages.sdp.sdp_flag import SDPFlag
from spinnman.messages.sdp.sdp_header import SDPHeader
from spinnman.messages.sdp.sdp_message import SDPMessage
from spinnman.model.cpu_state import CPUState

from pacman.utilities.utility_objs.progress_bar import ProgressBar

import struct


class FrontEndCommonApplicationExiter(object):
    """
    FrontEndCommonApplicationExiter
    """

    def __call__(self, app_id, txrx, executable_targets, no_sync_changes):

        txrx.stop_application(app_id)