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

from spinn_utilities.progress_bar import ProgressBar
from spinnman.constants import MAX_TAG_ID
from spinn_front_end_common.data import FecDataView


def tags_loader():
    """
    Loads tags onto the machine.
    """
    # clear all the tags from the Ethernet connection, as nothing should
    # be allowed to use it (no two apps should use the same Ethernet
    # connection at the same time)
    transceiver = FecDataView.get_transceiver()
    progress = ProgressBar(MAX_TAG_ID, "Clearing tags")
    for tag_id in progress.over(range(MAX_TAG_ID)):
        transceiver.clear_ip_tag(tag_id)

    # Use tags object to supply tag info if it is supplied
    tags = FecDataView.get_tags()
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
