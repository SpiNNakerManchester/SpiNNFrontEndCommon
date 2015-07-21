from abc import ABCMeta
from spinnman.messages.eieio.eieio_parameters import EIEIOParameters
from spynnaker.pyNN import exceptions
from spinn_front_end_common.utility_models.live_packet_gather_parameters \
     import LivePacketGatherParameters

"""
                 port, board_address=None, tag=None, key_prefix=None, 
                 prefix_type=None,

                 virtual_key=None, check_key=True, key_left_shift=0,
                 sdp_port=1, buffer_space=0, notify_buffer_space=False,
                 space_before_notification=0, notification_tag=None,
                 notification_ip_address=None, notification_port=None,
                 notification_strip_sdp=True

                 ip_address, strip_sdp=True, use_prefix=False,
                 message_type=EIEIOType.KEY_32_BIT, right_shift=0, 
                 payload_as_time_stamps=True, use_payload_prefix=True, 
                 payload_prefix=None, payload_right_shift=0,
                 number_of_packets_sent_per_time_step=0

"""

class ReverseIPTagParameters(EIEIOParameters):

    def __init__(self, port, ip_address=None, tag=None, key_prefix=None,
                 prefix_type=None, virtual_key=None, check_key=True,
                 key_left_shift=0, sdp_port=1, buffer_space=0,
                 notify_buffer_space=False, space_before_notification=0,
                 notification_tag=None, notification_ip_address=None,
                 notification_port=None, notification_strip_sdp=True, **args):

        EIEIOParameters.__init__(self, port=port, ip_address=ip_address, 
                                 board=ip_address, tag=tag, 
                                 key_prefix=key_prefix, prefix_type=prefix_type)

        # basic check on virtual key
        if (virtual_key is not None) and (virtual_key < 0):
           raise exceptions.ConfigurationException(
                            "Virtual keys must be positive")
        else:
           self._virtual_key = virtual_key
        if key_left_shift > 16 or key_left_shift < 0:
           raise exceptions.ConfigurationException(
               "the key left shift must be within the range of "
               "0 to 16. Please change this parameter and try again")
        self._key_left_shift = key_left_shift
        self._check_key = check_key
        self._sdp_port = sdp_port
        self._buffer_space = buffer_space
        self._notify_buffer_space = notify_buffer_space
        self._space_before_notification = space_before_notification
        self._notification_iptag_params = LivePacketGatherParameters(
                                          port=notification_port,
                                          ip_address=notification_ip_address,
                                          tag=notification_tag,
                                          board=ip_address,
                                          strip_sdp=notification_strip_sdp)
     
    @property
    def virtual_key(self):
        return self._virtual_key

    @virtual_key.setter
    def virtual_key(self, virtual_key):
        self._virtual_key = virtual_key

    @property
    def check_key(self):
        return self._check_key

    @property
    def key_left_shift(self):
        return self._key_left_shift   

    @property
    def sdp_port(self):
        return self._sdp_port

    @property
    def buffer_space(self):
        return self._buffer_space 

    @property
    def notify_buffer_space(self):
        return self._notify_buffer_space   

    @property
    def space_before_notification(self):
        return self._space_before_notification

    @property
    def notification_iptag_params(self):
        return self._notification_iptag_params
