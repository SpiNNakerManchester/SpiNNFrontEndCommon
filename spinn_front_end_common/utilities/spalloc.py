# Copyright (c) 2021 The University of Manchester
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
from urllib.parse import urlparse


def parse_old_spalloc(
        spalloc_server, spalloc_port=22244, spalloc_user="unknown user"):
    """
    Parse a URL to the old-style service. This may take the form:

        spalloc://user@spalloc.host.example.com:22244

    The leading ``spalloc://`` is the mandatory part (as is the actual host
    name). If the port and user are omitted, the defaults given in the other
    arguments are used (or default defaults).

    A bare hostname can be used instead. If that's the case (i.e., there's no
    ``spalloc://`` prefix) then the port and user are definitely used.

    :param str spalloc_server: Hostname or URL
    :param int spalloc_port: Default port
    :param str spalloc_user: Default user
    :return: hostname, port, username
    :rtype: tuple(str,int,str)
    """
    if spalloc_port is None or spalloc_port == "":
        spalloc_port = 22244
    if spalloc_user is None or spalloc_user == "":
        spalloc_user = "unknown user"
    parsed = urlparse(spalloc_server, "spalloc")
    if parsed.netloc == "":
        return spalloc_server, spalloc_port, spalloc_user
    return parsed.hostname, (parsed.port or spalloc_port), \
        (parsed.username or spalloc_user)
