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

from collections import deque
from threading import Lock
import logging
from spinn_utilities.log import FormatAdapter
from spinnman.messages.eieio.command_messages import (
    EventStopRequest, HostSendSequencedData)
from spinn_front_end_common.utilities.exceptions import SpinnFrontEndException

logger = FormatAdapter(logging.getLogger(__name__))

#: The total number of sequence numbers
_N_SEQUENCES = 256


class BuffersSentDeque(object):
    """
    A tracker of buffers sent / to send for a region
    """

    __slots__ = [
        #: The region being managed
        "_region",

        #: A queue of messages sent, ordered by sequence number
        "_buffers_sent",

        #: The current sequence number of the region
        "_sequence_number",

        #: A lock for the sequence number
        "_sequence_lock",

        #: The last sequence number to be received on the machine
        "_last_received_sequence_number",

        #: True if the stop message has been sent
        "_sent_stop_message",

        #: The number of sequence numbers allowed in a single transmission
        "_n_sequences_per_transmission"
    ]

    def __init__(self, region, sent_stop_message=False,
                 n_sequences_per_tranmission=64):
        """
        :param int region: The region being managed
        :param bool sent_stop_message: True if the stop message has been sent
        :param int n_sequences_per_tranmission:
            The number of sequences allowed in each transmission set
        """
        self._region = region
        self._buffers_sent = deque(maxlen=n_sequences_per_tranmission)
        self._sequence_number = 0
        self._sequence_lock = Lock()
        self._last_received_sequence_number = _N_SEQUENCES - 1
        self._sent_stop_message = sent_stop_message
        self._n_sequences_per_transmission = n_sequences_per_tranmission

    @property
    def is_full(self):
        """
        Whether the number of messages sent is at the limit for the
        sequencing system.

        :rtype: bool
        """
        return len(self._buffers_sent) >= self._n_sequences_per_transmission

    def is_empty(self):
        """
        Determine if there are no messages.

        :rtype: int
        """
        return len(self._buffers_sent) == 0

    def send_stop_message(self):
        """
        Send a message to indicate the end of all the messages.
        """
        if not self._sent_stop_message:
            self._sent_stop_message = True
            self.add_message_to_send(EventStopRequest())

    def add_message_to_send(self, message):
        """
        Add a message to send.  The message is converted to a sequenced
        message.

        :param message: The message to be added
        :type message:
            ~spinnman.messages.eieio.abstract_messages.AbstractEIEIOMessage
        """

        # If full, raise an exception
        if self.is_full:
            raise SpinnFrontEndException("The buffer is full")

        # Create a sequenced message and update the sequence number
        self._sequence_lock.acquire()
        sequenced_message = HostSendSequencedData(
            self._region, self._sequence_number, message)
        self._sequence_number = (self._sequence_number + 1) % _N_SEQUENCES
        self._sequence_lock.release()

        # Add the sequenced message to the buffers
        self._buffers_sent.append(sequenced_message)

    @property
    def messages(self):
        """
        The messages that have been added to the set.

        :rtype:
            iterable(~spinnman.messages.eieio.command_messages.HostSendSequencedData)
        """
        return self._buffers_sent

    def update_last_received_sequence_number(self, last_received_sequence_no):
        """
        Updates the last received sequence number.  If the sequence number is
        within the valid window, packets before the sequence number within the
        window are removed, and the last received sequence number is updated,
        thus moving the window for the next call.  If the sequence number is
        not within the valid window, it is assumed to be invalid and so is
        ignored.

        :param int last_received_sequence_no: The new sequence number
        :return: True if update went ahead, False if it was ignored
        :rtype: bool
        """

        # The sequence number window is between the last received and
        # the last received + window size, taking account that the end
        # of the window might wrap
        min_seq_no_acceptable = self._last_received_sequence_number
        max_seq_no_acceptable = (
            (min_seq_no_acceptable + self._n_sequences_per_transmission)
            % _N_SEQUENCES)

        if (min_seq_no_acceptable <= last_received_sequence_no <=
                max_seq_no_acceptable):

            # The sequence hasn't wrapped and the sequence is valid
            self._last_received_sequence_number = last_received_sequence_no
            self._remove_messages()
            return True
        elif max_seq_no_acceptable < min_seq_no_acceptable:

            # The sequence has wrapped
            if (0 <= last_received_sequence_no <= max_seq_no_acceptable or
                    min_seq_no_acceptable <= last_received_sequence_no <=
                    _N_SEQUENCES):

                # The sequence is in the valid range
                self._last_received_sequence_number = last_received_sequence_no
                self._remove_messages()
                return True

        # If none of the above match, the sequence is out of the window
        return False

    def _remove_messages(self):
        """
        Remove messages that are no longer relevant, based on the last
        sequence number received.
        """
        min_sequence = (self._last_received_sequence_number -
                        self._n_sequences_per_transmission)
        logger.debug("Removing buffers between {} and {}",
                     min_sequence, self._last_received_sequence_number)

        # If we are at the start of the sequence numbers, keep going back up to
        # the allowed window
        if min_sequence < 0:
            back_min_sequence = min_sequence + _N_SEQUENCES
            while (self._buffers_sent and
                    self._buffers_sent[0].sequence_no > back_min_sequence):
                logger.debug("Removing buffer with sequence {}",
                             self._buffers_sent[0].sequence_no)
                self._buffers_sent.popleft()

        # Go back through the queue until we reach the last received sequence
        while (self._buffers_sent and
                min_sequence < self._buffers_sent[0].sequence_no <=
                self._last_received_sequence_number):
            logger.debug("Removing buffer with sequence {}",
                         self._buffers_sent[0].sequence_no)
            self._buffers_sent.popleft()
