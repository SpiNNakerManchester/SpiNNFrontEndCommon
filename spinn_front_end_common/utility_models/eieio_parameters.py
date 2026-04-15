# Copyright (c) 2015 The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import List, Optional, Union
from dataclasses import dataclass

import numpy

from spinnman.messages.eieio import EIEIOPrefix
from spinnman.model.enums import SDP_PORTS

_SendBufferTimes = Optional[Union[numpy.ndarray, List[numpy.ndarray]]]


@dataclass(frozen=False)
class EIEIOParameters:
    """
    :param board_address:
        The IP address of the board on which to place this vertex if receiving
        data, either buffered or live (by default, any board is chosen)
    :param receive_port:
        The port on the board that will listen for incoming event packets
        (default is to disable this feature; set a value to enable it, or set
        the `reserve_reverse_ip_tag parameter` to True if a random port is to
        be used)
    :param receive_sdp_port:
        The SDP port to listen on for incoming event packets (defaults to 1)
    :param receive_tag:
        The IP tag to use for receiving live events (uses any by default)
    :param receive_rate:
    :param virtual_key:
        The base multicast key to send received events with (assigned
        automatically by default)
    :param prefix:
        The prefix to "or" with generated multicast keys (default is no prefix)
    :param prefix_type:
        Whether the prefix should apply to the upper or lower half of the
        multicast keys (default is upper half)
    :param check_keys:
        True if the keys of received events should be verified before sending
        (default False)
    :param reserve_reverse_ip_tag:
        True if the source should set up a tag through which it can receive
        packets; if port is set to `None` this can be used to enable the
        reception of packets on a randomly assigned port, which can be read
        from the database
    """
    receive_port: Optional[int] = None
    receive_sdp_port: int = SDP_PORTS.INPUT_BUFFERING_SDP_PORT.value
    receive_tag: Optional[int] = None
    receive_rate: float = 10.0
    virtual_key: Optional[int] = None
    prefix: Optional[int] = None
    prefix_type: Optional[EIEIOPrefix] = None
    check_keys: bool = False
    reserve_reverse_ip_tag: bool = False
