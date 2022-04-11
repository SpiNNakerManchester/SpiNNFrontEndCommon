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
from enum import IntEnum
from functools import wraps
from logging import getLogger
from multiprocessing import Process, Queue
from packaging.version import Version
import queue
import re
import requests
import struct
import threading
from urllib.parse import urlparse, urlunparse
import websocket
from spinn_utilities.abstract_base import abstractmethod
from spinn_utilities.abstract_context_manager import AbstractContextManager
from spinn_utilities.log import FormatAdapter
from spinn_utilities.overrides import overrides
from spinnman.connections.abstract_classes import (
    Connection, Listenable, SDPReceiver, SDPSender, SCPReceiver, SCPSender)
from spinnman.connections.udp_packet_connections import (
    update_sdp_header_for_udp_send)
from spinnman.constants import SCP_SCAMP_PORT
from spinnman.exceptions import SpinnmanTimeoutException
from spinnman.messages.sdp import SDPMessage, SDPFlag
from spinnman.messages.scp.enums import SCPResult
from spalloc.protocol_client import ProtocolError

logger = FormatAdapter(getLogger(__name__))
_S = "JSESSIONID"
#: Enable detailed debugging by setting to True
_debug_pretty_print = False

_open_req = struct.Struct("<IIIII")
_close_req = struct.Struct("<III")
# Open and close share the response structure
_open_close_res = struct.Struct("<III")
_msg = struct.Struct("<II")
_TWO_SHORTS = struct.Struct("<2H")


class SpallocState(IntEnum):
    #: The job is in an unknown state.
    UNKNOWN = 0
    #: The job is queued waiting for allocation.
    QUEUED = 1
    #: The job is queued waiting for boards to power on or off.
    POWER = 2
    #: The job is ready for user code to run on it.
    READY = 3
    #: The job has been destroyed.
    DESTROYED = 4


class _ProxyProtocol(IntEnum):
    #: Message relating to opening a channel
    OPEN = 0
    #: Message relating to closing a channel
    CLOSE = 1
    #: Message sent on a channel
    MSG = 2


def _clean_url(url):
    """
    Add a ``/`` to the end of the path part of a URL if there isn't one.

    :param str url:
    :rtype: str
    """
    r = urlparse(url)
    parts = list(r)
    # Add a / to the end of the path if it isn't there
    if not parts[2].endswith("/"):
        parts[2] += "/"
    return urlunparse(parts)


def _may_renew(method):
    def pp_req(req):
        """
        :param ~requests.PreparedRequest req:
        """
        print('{}\n{}\r\n{}\r\n\r\n{}'.format(
            '>>>>>>>>>>>START>>>>>>>>>>>',
            req.method + ' ' + req.url,
            '\r\n'.join('{}: {}'.format(*kv) for kv in req.headers.items()),
            req.body if req.body else ""))

    def pp_resp(resp):
        """
        :param ~requests.Response resp:
        """
        print('{}\n{}\r\n{}\r\n\r\n{}'.format(
            '<<<<<<<<<<<START<<<<<<<<<<<',
            str(resp.status_code) + " " + resp.reason,
            '\r\n'.join('{}: {}'.format(*kv) for kv in resp.headers.items()),
            # Assume we only get textual responses
            str(resp.content, "UTF-8") if resp.content else ""))

    @wraps(method)
    def call(self, *args, **kwargs):
        renew_count = 0
        while True:
            r = method(self, *args, **kwargs)
            if _debug_pretty_print:
                pp_req(r.request)
                pp_resp(r)
            if _S in r.cookies:
                self._session_id = r.cookies[_S]
            if r.status_code != 401 or not renew_count:
                return r
            self.renew()
            renew_count += 1

    return call


class _Session:
    __slots__ = (
        "__login_form_url", "__login_submit_url", "__srv_base",
        "__username", "__password", "__token",
        "_session_id", "__csrf", "__csrf_header")

    def __init__(self, service_url, username, password, token):
        """
        :param str service_url: The reference to the service.
            *Should not* include a username or password in it.
        :param str username: The user name to use
        :param str password: The password to use
        :param str token: The bearer token to use
        """
        url = _clean_url(service_url)
        self.__login_form_url = url + "system/login.html"
        self.__login_submit_url = url + "system/perform_login"
        self.__srv_base = url + "srv/spalloc/"
        self.__username = username
        self.__password = password
        self.__token = token

    @_may_renew
    def get(self, url, **kwargs):
        """
        Do an HTTP ``GET`` in the session.

        :param str url:
        :rtype: ~requests.Response
        """
        params = kwargs if kwargs else None
        cookies = {_S: self._session_id}
        r = requests.get(url, params=params, cookies=cookies,
                         allow_redirects=False)
        logger.debug("GET {} returned {}", url, r.status_code)
        return r

    @_may_renew
    def post(self, url, jsonobj, **kwargs):
        """
        Do an HTTP ``POST`` in the session.

        :param str url:
        :param dict jsonobj:
        :rtype: ~requests.Response
        """
        params = kwargs if kwargs else None
        cookies, headers = self._credentials
        r = requests.post(url, params=params, json=jsonobj,
                          cookies=cookies, headers=headers,
                          allow_redirects=False)
        logger.debug("POST {} returned {}", url, r.status_code)
        return r

    @_may_renew
    def put(self, url, data, **kwargs):
        """
        Do an HTTP ``PUT`` in the session. Puts plain text *OR* JSON!

        :param str url:
        :param str data:
        :rtype: ~requests.Response
        """
        params = kwargs if kwargs else None
        cookies, headers = self._credentials
        if isinstance(data, str):
            headers["Content-Type"] = "text/plain; charset=UTF-8"
        r = requests.put(url, params=params, data=data,
                         cookies=cookies, headers=headers,
                         allow_redirects=False)
        logger.debug("PUT {} returned {}", url, r.status_code)
        return r

    @_may_renew
    def delete(self, url, **kwargs):
        """
        Do an HTTP ``DELETE`` in the session.

        :param str url:
        :rtype: ~requests.Response
        """
        params = kwargs if kwargs else None
        cookies, headers = self._credentials
        r = requests.delete(url, params=params, cookies=cookies,
                            headers=headers, allow_redirects=False)
        logger.debug("DELETE {} returned {}", url, r.status_code)
        return r

    def renew(self):
        """
        Renews the session, logging the user into it so that state modification
        operations can be performed.

        :returns: Description of the root of the service, without CSRF data
        :rtype: dict
        """
        if self.__token:
            r = requests.get(self.__login_form_url, allow_redirects=False)
            self._session_id = r.cookies[_S]
        else:
            # Step one: a temporary session so we can log in
            csrf_matcher = re.compile(
                r"""<input type="hidden" name="_csrf" value="(.*)" />""")
            r = requests.get(self.__login_form_url, allow_redirects=False)
            logger.debug("GET {} returned {}",
                         self.__login_form_url, r.status_code)
            m = csrf_matcher.search(r.text)
            if not m:
                raise Exception("could not establish temporary session")
            csrf = m.group(1)
            session = r.cookies[_S]

            # Step two: actually do the log in
            form = {
                "_csrf": csrf,
                "username": self.__username,
                "password": self.__password,
                "submit": "submit"
            }
            # NB: returns redirect that sets a cookie
            r = requests.post(self.__login_submit_url,
                              cookies={_S: session}, allow_redirects=False,
                              data=form)
            logger.debug("POST {} returned {}",
                         self.__login_submit_url, r.status_code)
            self._session_id = r.cookies[_S]
            # We don't need to follow that redirect

        # Step three: get the basic service data and new CSRF token
        obj = self.get(self.__srv_base).json()
        self.__csrf_header = obj["csrf-header"]
        self.__csrf = obj["csrf-token"]
        del obj["csrf-header"]
        del obj["csrf-token"]
        return obj

    @property
    def _credentials(self):
        """
        The credentials for requests. *Serializable.*
        """
        cookies = {_S: self._session_id}
        headers = {self.__csrf_header: self.__csrf}
        if self.__token:
            # This would be better off done once per session only
            headers["Authorization"] = f"Bearer {self.__token}"
        return cookies, headers

    def websocket(self, url, header=None, cookie=None, **kwargs):
        """
        Create a websocket that uses the session credentials to establish
        itself.

        :param str url: Actual location to open websocket at
        :param dict(str,str) header: Optional HTTP headers
        :param str cookie:
            Optional cookies (composed as semicolon-separated string)
        :param kwargs: Other options to :py:func:`~websocket.create_connection`
        :rtype: ~websocket.WebSocket
        """
        # Note: *NOT* a renewable action!
        if header is None:
            header = {}
        header[self.__csrf_header] = self.__csrf
        if cookie is not None:
            cookie += ";"
        cookie += _S + "=" + self._session_id
        return websocket.create_connection(
            url, header=header, cookie=cookie, **kwargs)

    def _purge(self):
        """
        Clears out all credentials from this session, rendering the session
        completely inoperable henceforth.
        """
        self.__username = None
        self.__password = None
        self._session_id = None
        self.__csrf = None


class SpallocClient(AbstractContextManager):
    """
    Basic client library for talking to new Spalloc.
    """
    __slots__ = ("__session",
                 "__machines_url", "__jobs_url", "version")

    @staticmethod
    def is_server_address(address, additional_schemes=()):
        """ Test if the given address is a likely spalloc server URL.

        :param str address: The address to check
        :param ~collections.abc.Iterable(str) additional_schemes:
            Any additional URL schemes that should be considered to be
            successes; typically ``{"spalloc"}`` when looser matching is
            required.
        :rtype: bool
        """
        schemes = {"http", "https"}
        if additional_schemes:
            schemes.update(additional_schemes)
        try:
            pieces = urlparse(address)
            scheme = pieces.scheme.lower()
            return scheme in schemes and pieces.netloc is not None
        except Exception:  # pylint: disable=broad-except
            return False

    def __init__(
            self, service_url, username=None, password=None,
            bearer_token=None):
        """
        :param str service_url: The reference to the service.
            May have username and password supplied as part of the network
            location; if so, the ``username`` and ``password`` arguments
            *must* be ``None``.
        :param str username: The user name to use
        :param str password: The password to use
        :param str bearer_token: The bearer token to use
        """
        if username is None and password is None:
            service_url, username, password = self.__parse_service_url(
                service_url)
        self.__session = _Session(
            service_url, username, password, bearer_token)
        if not bearer_token:
            obj = self.__session.renew()
        v = obj["version"]
        self.version = Version(
            f"{v['major-version']}.{v['minor-version']}.{v['revision']}")
        self.__machines_url = obj["machines-ref"]
        self.__jobs_url = obj["jobs-ref"]
        logger.info("established session to {} for {}", service_url, username)

    @staticmethod
    def __parse_service_url(url):
        """
        Parses a combined service reference.

        :param str url:
        :rtype: tuple(str,str,str)
        """
        pieces = urlparse(url)
        user = pieces.username
        password = pieces.password
        netloc = pieces.hostname
        if pieces.port is not None:
            netloc += f":{pieces.port}"
        url = urlunparse((
            pieces.scheme, netloc, pieces.path, None, None, None))
        return url, user, password

    def list_machines(self):
        """
        Get the machines supported by the server.

        :return:
            Mapping from machine names to handles for working with a machine.
        :rtype: dict(str,SpallocMachine)
        """
        obj = self.__session.get(self.__machines_url).json()
        return {m["name"]: SpallocMachine(self, m) for m in obj["machines"]}

    def list_jobs(self, deleted=False):
        """
        Get the jobs known to the server.

        :param bool deleted: Whether to include deleted jobs.
        :return: The jobs known to the server.
        :rtype: ~typing.Iterable(SpallocJob)
        """
        obj = self.__session.get(
            self.__jobs_url,
            deleted=("true" if deleted else "false")).json()
        while obj["jobs"]:
            for u in obj["jobs"]:
                yield SpallocJob(self.__session, u)
            if "next" not in obj:
                break
            obj = self.__session.get(obj["next"]).json()

    def create_job(self, num_boards=1, machine_name=None, keepalive=45):
        """
        Create a job with a specified number of boards.

        :param int num_boards:
            How many boards to ask for (defaults to 1)
        :param str machine_name:
            Which machine to run on? If omitted, the service's machine tagged
            with ``default`` will be used.
        :param int keepalive:
            After how many seconds of no activity should a job become eligible
            for automatic pruning?
        :return: A handle for monitoring and interacting with the job.
        :rtype: SpallocJob
        """
        create = {
            "num-boards": int(num_boards),
            "keepalive-interval": f"PT{int(keepalive)}S"
        }
        if machine_name:
            create["machine-name"] = machine_name
        else:
            create["tags"] = ["default"]
        r = self.__session.post(self.__jobs_url, create)
        url = r.headers["Location"]
        return SpallocJob(self.__session, url)

    def create_job_rect(self, width, height, machine_name=None, keepalive=45):
        """
        Create a job with a rectangle of boards.

        :param int width:
            The width of rectangle to request
        :param int height:
            The height of rectangle to request
        :param str machine_name:
            Which machine to run on? If omitted, the service's machine tagged
            with ``default`` will be used.
        :param int keepalive:
            After how many seconds of no activity should a job become eligible
            for automatic pruning?
        :return: A handle for monitoring and interacting with the job.
        :rtype: SpallocJob
        """
        create = {
            "dimensions": {
                "width": int(width),
                "height": int(height)
            },
            "keepalive-interval": f"PT{int(keepalive)}S"
        }
        if machine_name:
            create["machine-name"] = machine_name
        else:
            create["tags"] = ["default"]
        r = self.__session.post(self.__jobs_url, create)
        url = r.headers["Location"]
        return SpallocJob(self.__session, url)

    def create_job_board(
            self, triad=None, physical=None, ip_address=None,
            machine_name=None, keepalive=45):
        """
        Create a job with a rectangle of boards.

        :param tuple(int,int,int) triad:
            The logical coordinate of the board to request
        :param tuple(int,int,int) physical:
            The physical coordinate of the board to request
        :param str ip_address:
            The IP address of the board to request
        :param str machine_name:
            Which machine to run on? If omitted, the service's machine tagged
            with ``default`` will be used.
        :param int keepalive:
            After how many seconds of no activity should a job become eligible
            for automatic pruning?
        :return: A handle for monitoring and interacting with the job.
        :rtype: SpallocJob
        """
        if triad:
            x, y, z = triad
            board = {"x": x, "y": y, "z": z}
        elif physical:
            c, f, b = physical
            board = {"cabinet": c, "frame": f, "board": b}
        elif ip_address:
            board = {"address": str(ip_address)}
        else:
            raise KeyError("at least one of triad, physical and ip_address "
                           "must be given")
        create = {
            "board": board,
            "keepalive-interval": f"PT{int(keepalive)}S"
        }
        if machine_name:
            create["machine-name"] = machine_name
        else:
            create["tags"] = ["default"]
        r = self.__session.post(self.__jobs_url, create)
        url = r.headers["Location"]
        return SpallocJob(self.__session, url)

    def close(self):
        if self.__session is not None:
            self.__session._purge()
        self.__session = None


def _SpallocKeepalive(url, interval, term_queue, cookies, headers):
    """
    Actual keepalive task implementation. Don't use directly.
    """
    headers["Content-Type"] = "text/plain; charset=UTF-8"
    while True:
        requests.put(url, data="alive", cookies=cookies, headers=headers,
                     allow_redirects=False)
        try:
            term_queue.get(True, interval)
            break
        except queue.Empty:
            continue


class _SpallocSessionAware:
    """
    Connects to the session.
    """
    __slots__ = ("__session", "_url")

    def __init__(self, session, url):
        self.__session = session
        self._url = _clean_url(url)

    @property
    def _session_credentials(self):
        """
        Get the current session credentials.
        Only supposed to be called by subclasses.

        :rtype: tuple(dict(str,str),dict(str,str))
        """
        return self.__session._credentials

    def _get(self, url, **kwargs):
        return self.__session.get(url, **kwargs)

    def _post(self, url, jsonobj, **kwargs):
        return self.__session.post(url, jsonobj, **kwargs)

    def _put(self, url, data, **kwargs):
        return self.__session.put(url, data, **kwargs)

    def _delete(self, url, **kwargs):
        return self.__session.delete(url, **kwargs)

    def _websocket(self, url, **kwargs):
        """
        Create a websocket that uses the session credentials to establish
        itself.

        :param str url: Actual location to open websocket at
        :rtype: ~websocket.WebSocket
        """
        return self.__session.websocket(url, **kwargs)


class SpallocMachine(_SpallocSessionAware):
    """
    Represents a spalloc-controlled machine.

    Don't make this yourself. Use :py:class:`SpallocClient` instead.
    """
    __slots__ = ("name", "tags", "width", "height",
                 "dead_boards", "dead_links")

    def __init__(self, session, machine_data):
        """
        :param _Session session:
        :param dict machine_data:
        """
        super().__init__(session, machine_data["uri"])
        #: The name of the machine.
        self.name = machine_data["name"]
        #: The tags of the machine.
        self.tags = frozenset(machine_data["tags"])
        #: The width of the machine, in boards.
        self.width = machine_data["width"]
        #: The height of the machine, in boards.
        self.height = machine_data["height"]
        #: The dead or out-of-service boards of the machine.
        self.dead_boards = machine_data["dead-boards"]
        #: The dead or out-of-service links of the machine.
        self.dead_links = machine_data["dead-links"]

    @property
    def area(self):
        """
        Area of machine, in boards.

        :return: width, height
        :rtype: tuple(int,int)
        """
        return (self.width, self.height)

    def __repr__(self):
        return "SpallocMachine" + str((
            self.name, self.tags, self.width, self.height, self.dead_boards,
            self.dead_links))


class _ProxyReceiver(threading.Thread):
    def __init__(self, ws):
        super().__init__(daemon=True)
        self.__ws = ws
        self.__returns = {}
        self.__handlers = {}
        self.__correlation_id = 0
        self.start()

    def run(self):
        while self.__ws.connected:
            try:
                msg = self.__ws.recv_data()
            except Exception:  # pylint: disable=broad-except
                break
            code, num = _msg.unpack_from(msg, 0)
            if code in (_ProxyProtocol.OPEN, _ProxyProtocol.CLOSE):
                self.dispatch_return(num, msg)
            else:
                self.dispatch_message(num, msg)

    def expect_return(self, handler):
        c = self.__correlation_id
        self.__correlation_id += 1
        self.__returns[c] = handler
        return c

    def listen(self, channel_id, handler):
        self.__handlers[channel_id] = handler

    def dispatch_return(self, correlation_id, msg):
        handler = self.__returns.pop(correlation_id, None)
        if handler:
            handler(msg)

    def dispatch_message(self, channel_id, msg):
        handler = self.__handlers.get(channel_id, None)
        if handler:
            handler(msg)


class SpallocJob(_SpallocSessionAware):
    """
    Represents a job in spalloc.

    Don't make this yourself. Use :py:class:`SpallocClient` instead.
    """
    __slots__ = ("__machine_url", "__chip_url",
                 "_keepalive_url", "__keepalive_handle", "__proxy_handle",
                 "__proxy_thread")

    def __init__(self, session, job_handle):
        """
        :param _Session session:
        :param str job_handle:
        """
        super().__init__(session, job_handle)
        logger.info("established job at {}", job_handle)
        self.__machine_url = self._url + "machine"
        self.__chip_url = self._url + "chip"
        self._keepalive_url = self._url + "keepalive"
        self.__keepalive_handle = None
        self.__proxy_handle = None
        self.__proxy_thread = None

    def get_state(self):
        """
        Get the current state of the machine.

        :rtype: SpallocState
        """
        obj = self._get(self._url).json()
        return SpallocState[obj["state"]]

    def get_root_host(self):
        """
        Get the IP address for talking to the machine.

        :return: The IP address, or ``None`` if not allocated.
        :rtype: str or None
        """
        r = self._get(self.__machine_url)
        if r.status_code == 204:
            return None
        obj = r.json()
        for c in obj["connections"]:
            [x, y], host = c
            if x == 0 and y == 0:
                return host
        return None

    def get_connections(self):
        """
        Get the mapping from board coordinates to IP addresses.

        :return: (x,y)->IP mapping, or ``None`` if not allocated
        :rtype: dict(tuple(int,int), str) or None
        """
        r = self._get(self.__machine_url)
        if r.status_code == 204:
            return None
        return {
            (int(x), int(y)): str(host)
            for ((x, y), host) in r.json()["connections"]
        }

    @property
    def __proxy_url(self):
        """
        Get the URL for talking to the proxy connection system.
        """
        r = self._get(self._url)
        if r.status_code == 204:
            return None
        try:
            return r.json().proxy_ref
        except KeyError:
            return None

    def __init_proxy(self):
        if self.__proxy_handle is None or not self.__proxy_handle.connected:
            self.__proxy_handle = self._websocket(self.__proxy_url)
            self.__proxy_thread = _ProxyReceiver(self.__proxy_handle)

    def connect_to_board(self, x, y, port=SCP_SCAMP_PORT):
        """
        Open a connection to a particular board in the job.

        :param int x: X coordinate of the board's ethernet chip
        :param int y: Y coordinate of the board's ethernet chip
        :param int port: UDP port to talk to; defaults to the SCP port
        :return: A connection that talks to the board.
        :rtype: SpallocProxiedConnection
        """
        # TODO: return type
        self.__init_proxy()
        return _SpallocSocket(
            self.__proxy_handle, self.__proxy_thread, x, y, port)

    def wait_for_state_change(self, old_state):
        """
        Wait until the allocation is not in the given old state.

        :param SpallocState old_state:
            The state that we are looking to change out of.
        :return: The state that the allocation is now in. Note that if the
            machine gets destroyed, this will not wait for it.
        :rtype: SpallocState
        """
        while old_state != SpallocState.DESTROYED:
            obj = self._get(self._url, wait="true").json()
            s = SpallocState[obj["state"]]
            if s != old_state or s == SpallocState.DESTROYED:
                return s
        return old_state

    def wait_until_ready(self):
        """
        Wait until the allocation is in the ``READY`` state.

        :raises Exception: If the allocation is destroyed
        """
        state = SpallocState.UNKNOWN
        while state != SpallocState.READY:
            state = self.wait_for_state_change(state)
            if state == SpallocState.DESTROYED:
                raise Exception("job was unexpectedly destroyed")

    def destroy(self, reason="finished"):
        """
        Destroy the job.

        :param str reason: Why the job is being destroyed.
        """
        if self.__keepalive_handle:
            self.__keepalive_handle.close()
            self.__keepalive_handle = None
        self._delete(self._url, reason=reason)
        logger.info("deleted job at {}", self._url)

    def keepalive(self):
        """
        Signal the job that we want it to stay alive for a while longer.
        """
        self._put(self._keepalive_url, "alive")

    def launch_keepalive_task(self, period=30):
        """
        Starts a periodic task to keep a job alive.

        Tricky! *Cannot* be done with a thread, as the main thread is known
        to do significant amounts of CPU-intensive work.

        :param SpallocJob job:
            The job to keep alive
        :param int period:
            How often to send a keepalive message (in seconds)
        :return:
            Some kind of closeable task handle; closing it terminates the task.
            Destroying the job will also terminate the task.
        """
        class Closer:
            def __init__(self):
                self._queue = Queue(1)

            def close(self):
                self._queue.put("quit")

        self._keepalive_handle = Closer()
        p = Process(target=_SpallocKeepalive, args=(
            self._keepalive_url, period, self._keepalive_handle._queue,
            *self._session_credentials), daemon=True)
        p.start()
        return self._keepalive_handle

    def where_is_machine(self, x, y):
        """
        Get the *physical* coordinates of the board hosting the given chip.

        :param int x: Chip X coordinate
        :param int y: Chip Y coordinate
        :return: physical board coordinates (cabinet, frame, board), or
            ``None`` if there are no boards currently allocated to the job or
            the chip lies outside the allocation.
        :rtype: tuple(int,int,int) or None
        """
        r = self._get(self.__chip_url, x=int(x), y=int(y))
        if r.status_code == 204:
            return None
        return tuple(r.json()["physical-board-coordinates"])

    @property
    def _keepalive_handle(self):
        return self.__keepalive_handle

    @_keepalive_handle.setter
    def _keepalive_handle(self, handle):
        if self.__keepalive_handle is not None:
            raise Exception("cannot keep job alive from two tasks")
        self.__keepalive_handle = handle

    def __repr__(self):
        return f"SpallocJob({self._url})"


class SpallocProxiedConnection(
        SDPReceiver, SDPSender, SCPSender, SCPReceiver, Listenable):
    """
    The socket interface supported by proxied sockets. The socket will always
    be talking to a specific board. This emulates a SCAMPConnection.
    """
    __slots__ = ()

    @abstractmethod
    def send(self, message: bytes):
        """
        Send a message on an open socket.

        :param message: The message to send.
        """

    @abstractmethod
    def receive(self, timeout=None) -> bytes:
        """
        Receive a message on an open socket. Will block until a message is
        received.

        :param timeout:
            How long to wait for a message to be received before timing out.
            If None, will wait indefinitely (or until the connection is
            closed).
        :return: The received message.
        """

    @overrides(Listenable.get_receive_method)
    def get_receive_method(self):
        return self.receive_sdp_message

    @overrides(SDPReceiver.receive_sdp_message)
    def receive_sdp_message(self, timeout=None):
        data = self.receive(timeout)
        return SDPMessage.from_bytestring(data, 2)

    @overrides(SDPSender.send_sdp_message)
    def send_sdp_message(self, sdp_message):
        # If a reply is expected, the connection should
        if sdp_message.sdp_header.flags == SDPFlag.REPLY_EXPECTED:
            update_sdp_header_for_udp_send(
                sdp_message.sdp_header, self.chip_x, self.chip_y)
        else:
            update_sdp_header_for_udp_send(sdp_message.sdp_header, 0, 0)
        self.send(b'\0\0' + sdp_message.bytestring)

    @overrides(SCPReceiver.receive_scp_response)
    def receive_scp_response(self, timeout=1.0):
        data = self.receive(timeout)
        result, sequence = _TWO_SHORTS.unpack_from(data, 10)
        return SCPResult(result), sequence, data, 2

    @overrides(SCPSender.send_scp_request)
    def send_scp_request(self, scp_request):
        self.send(self.get_scp_data(scp_request))

    @overrides(SCPSender.get_scp_data)
    def get_scp_data(self, scp_request):
        update_sdp_header_for_udp_send(
            scp_request.sdp_header, self.chip_x, self.chip_y)
        return b'\0\0' + scp_request.bytestring


class _SpallocSocket(SpallocProxiedConnection):
    __slots__ = (
        "__ws", "__receiver", "__handle", "__msgs", "__current_msg",
        "__call_queue", "__call_lock", "_chip_x", "_chip_y")

    def __init__(
            self, ws: websocket.WebSocket, receiver: _ProxyReceiver,
            x: int, y: int, port: int):
        self._chip_x = x
        self._chip_y = y
        self.__ws = ws
        self.__receiver = receiver
        self.__msgs = queue.Queue()
        self.__current_msg = None
        self.__call_queue = queue.Queue(1)
        self.__call_lock = threading.RLock()
        self.__handle, = self.__call(
            _ProxyProtocol.OPEN, _open_req, _open_close_res, x, y, port)
        self.__receiver.listen(self.__handle, self.__msgs.put)

    def __call(self, proto: _ProxyProtocol, packer: struct.Struct,
               unpacker: struct.Struct, *args) -> list:
        if not self.is_connected:
            raise IOError("socket closed")
        with self.__call_lock:
            # All calls via websocket use correlation_id
            correlation_id = self.__receiver.expect_return(
                self.__call_queue.put)
            self.__ws.send_binary(packer.pack(proto, correlation_id, *args))
            return unpacker.unpack(self.__call_queue.get())[2:]

    @overrides(Connection.is_connected)
    def is_connected(self):
        return self.__ws and self.__ws.connected

    @overrides(Connection.close)
    def close(self):
        channel_id, = self.__call(
            _ProxyProtocol.CLOSE, _close_req, _open_close_res, self.__handle)
        if channel_id != self.__handle:
            raise ProtocolError("failed to close proxy socket")
        self.__ws = None
        self.__receiver = None

    @overrides(SpallocProxiedConnection.send)
    def send(self, message: bytes):
        if not self.is_connected:
            raise IOError("socket closed")
        # Put the header on the front and send it
        self.__ws.send_binary(_msg.pack(
            _ProxyProtocol.MSG, self.__handle) + message)

    def __get(self, timeout: float = 0.5) -> bytes:
        """
        Get a value from the queue. Handles block/non-block switching and
        trimming of the message protocol prefix.
        """
        if not timeout:
            return self.__msgs.get(block=False)[_msg.size:]
        else:
            return self.__msgs.get(timeout=timeout)[_msg.size:]

    @overrides(SpallocProxiedConnection.receive)
    def receive(self, timeout=None) -> bytes:
        if self.__current_msg is not None:
            try:
                return self.__current_msg
            finally:
                self.__current_msg = None
        if timeout is None:
            while True:
                try:
                    return self.__get()
                except queue.Empty:
                    pass
                if not self.is_connected:
                    raise IOError("socket closed")
        else:
            try:
                return self.__get(timeout)
            except queue.Empty as e:
                if not self.is_connected:
                    # pylint: disable=raise-missing-from
                    raise IOError("socket closed")
                raise SpinnmanTimeoutException("receive", timeout) from e

    @overrides(Listenable.is_ready_to_receive)
    def is_ready_to_receive(self, timeout=0) -> bool:
        # If we already have a message or the queue peek succeeds, return now
        if self.__current_msg is not None or self.__msgs.not_empty:
            return True
        try:
            self.__current_msg = self.__get(timeout)
            return True
        except queue.Empty:
            return False

    @property
    def chip_x(self):
        return self._chip_x

    @property
    def chip_y(self):
        return self._chip_y


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
