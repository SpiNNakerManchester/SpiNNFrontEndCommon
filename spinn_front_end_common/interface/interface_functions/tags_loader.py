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


def tags_loader(transceiver, tags):
    """ Loads tags onto the machine.

    :param ~spinnman.transceiver.Transceiver transceiver:
        the transceiver object
    :param ~pacman.model.tags.Tags tags:
        the tags object which contains IP and reverse IP tags;
        could be ``None`` if these are being given in separate lists
    """
    # clear all the tags from the Ethernet connection, as nothing should
    # be allowed to use it (no two apps should use the same Ethernet
    # connection at the same time)
    progress = ProgressBar(MAX_TAG_ID, "Clearing tags")
    for tag_id in progress.over(range(MAX_TAG_ID)):
        transceiver.clear_ip_tag(tag_id)

    # Use tags object to supply tag info if it is supplied
    iptags = list(tags.ip_tags)
    reverse_iptags = list(tags.reverse_ip_tags)

    # Load the IP tags and the Reverse IP tags
    progress = ProgressBar(
        len(iptags) + len(reverse_iptags), "Loading Tags")
    for ip_tag in progress.over(iptags, False):
        transceiver.set_ip_tag(ip_tag)
    for reverse_ip_tag in progress.over(reverse_iptags, False):
        transceiver.set_reverse_ip_tag(reverse_ip_tag)
    progress.end()
