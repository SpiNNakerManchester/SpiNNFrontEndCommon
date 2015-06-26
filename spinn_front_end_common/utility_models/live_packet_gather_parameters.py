from abc import ABCMeta
from spinnman.messages.eieio.eieio_type import EIEIOType
from spinnman.messages.eieio.eieio_parameters import EIEIOParameters
from spynnaker.pyNN import exceptions
from spynnaker.pyNN.utilities import conf

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

class LivePacketGatherParameters(EIEIOParameters):

    def __init__(self, port=None, ip_address=None, board=None, tag=None,
                 key_prefix=None, prefix_type=None, strip_sdp=True,
                 word_width=32, with_payload=False, right_shift=0,
                 payload_as_time_stamps=True, payload_prefix=0,
                 payload_right_shift=0,
                 number_of_packets_sent_per_time_step=0, **args):

        if port is None:
           port = conf.config.getint("Recording", "live_spike_port")
        if ip_address is None:
           ip_address = conf.config.get("Recording", "live_spike_host")

        EIEIOParameters.__init__(self, port, ip_address, board, tag, key_prefix,
                                 prefix_type)

        if payload_prefix is None:
           self._use_payload_prefix = False
           self._payload_prefix = 0
        else:
           self._use_payload_prefix = True
           self._payload_prefix = payload_prefix 
        if payload_as_time_stamps:
           if with_payload and self._use_payload_prefix:
              raise exceptions.ConfigurationException(
                                         "Timestamps can either be included as "
                                         "a payload prefix or as a payload to "
                                         "each key, not both")
           if not(with_payload or self._use_payload_prefix):
              raise exceptions.ConfigurationException(
                                         "Timestamps can either be included as "
                                         "a payload prefix or as a payload to "
                                         "each key, but the current "
                                         "configuration does not specify either "
                                         "of these")
        if word_width == 16:
           if with_payload: 
              self._message_type = EIEIOType.KEY_PAYLOAD_16_BIT
           else: 
              self._message_type = EIEIOType.KEY_16_BIT
        elif word_width == 32:
           if with_payload: 
              self._message_type = EIEIOType.KEY_PAYLOAD_32_BIT
           else: 
              self._message_type = EIEIOType.KEY_32_BIT
        else:
           raise exceptions.ConfigurationException(
                 "Unsupported recorder word width: %d specified" % word_width)
        self._payload_as_time_stamps = payload_as_time_stamps
        self._strip_sdp = strip_sdp
        self._right_shift = right_shift
        self._payload_right_shift = payload_right_shift 
        self._number_of_packets_sent_per_time_step = number_of_packets_sent_per_time_step
     
    @property
    def strip_sdp(self):
        return self._strip_sdp

    @property
    def message_type(self):
        return self._message_type

    @property
    def right_shift(self):
        return self._right_shift   

    @property
    def payload_as_time_stamps(self):
        return self._payload_as_time_stamps

    @property
    def use_payload_prefix(self):
        return self._use_payload_prefix 

    @property
    def payload_prefix(self):
        return self._payload_prefix   

    @property
    def payload_right_shift(self):
        return self._payload_right_shift

    @property
    def number_of_packets_sent_per_time_step(self):
        return self._number_of_packets_sent_per_time_step
