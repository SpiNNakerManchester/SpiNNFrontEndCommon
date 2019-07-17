# Copyright (c) 2017-2019 The University of Manchester
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from spinn_utilities.progress_bar import ProgressBar
from spinnman.constants import MAX_TAG_ID


class TagsLoader(object):
    """ Loads tags onto the machine
    """

    __slots__ = []

    def __call__(
            self, transceiver, tags=None, iptags=None, reverse_iptags=None):
        """
        :param tags: the tags object which contains IP and reverse IP tags;
            could be `None` if these are being given in separate lists
        :param iptags: a list of IP tags, given when tags is none
        :param reverse_iptags: a list of reverse IP tags when tags is none.
        :param transceiver: the transceiver object
        """
        # clear all the tags from the Ethernet connection, as nothing should
        # be allowed to use it (no two apps should use the same Ethernet
        # connection at the same time)
        progress = ProgressBar(MAX_TAG_ID, "Clearing tags")
        for tag_id in progress.over(range(MAX_TAG_ID)):
            transceiver.clear_ip_tag(tag_id)

        # Use tags object to supply tag info if it is supplied
        if tags is not None:
            iptags = list(tags.ip_tags)
            reverse_iptags = list(tags.reverse_ip_tags)

        # Load the IP tags and the Reverse IP tags
        progress = ProgressBar(
            len(iptags) + len(reverse_iptags), "Loading Tags")
        self.load_iptags(iptags, transceiver, progress)
        self.load_reverse_iptags(reverse_iptags, transceiver, progress)
        progress.end()

    @staticmethod
    def load_iptags(iptags, transceiver, progress_bar):
        """ Loads all the IP tags individually.

        :param iptags: the IP tags to be loaded.
        :param transceiver: the transceiver object
        :rtype: None
        """
        for ip_tag in progress_bar.over(iptags, False):
            transceiver.set_ip_tag(ip_tag)

    @staticmethod
    def load_reverse_iptags(reverse_ip_tags, transceiver, progress_bar):
        """ Loads all the reverse IP tags individually.

        :param reverse_ip_tags: the reverse IP tags to be loaded
        :param transceiver: the transceiver object
        :rtype: None
        """
        for reverse_ip_tag in progress_bar.over(reverse_ip_tags, False):
            transceiver.set_reverse_ip_tag(reverse_ip_tag)
