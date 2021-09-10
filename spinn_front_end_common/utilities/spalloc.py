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
from queue import Empty
import re
import requests
from urllib.parse import urlparse, urlunparse
from spinn_utilities.log import FormatAdapter

logger = FormatAdapter(getLogger(__name__))
_S = "JSESSIONID"
#: Enable detailed debugging by setting to True
_debug_pretty_print = False


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
        "__username", "__password",
        "_session_id", "__csrf", "__csrf_header")

    def __init__(self, service_url, username, password):
        """
        :param str service_url: The reference to the service.
            *Should not* include a username or password in it.
        :param str username: The user name to use
        :param str password: The password to use
        """
        url = _clean_url(service_url)
        self.__login_form_url = url + "system/login.html"
        self.__login_submit_url = url + "system/perform_login"
        self.__srv_base = url + "srv/spalloc/"
        self.__username = username
        self.__password = password

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
        return cookies, headers

    def _purge(self):
        """
        Clears out all credentials from this session, rendering the session
        completely inoperable henceforth.
        """
        self.__username = None
        self.__password = None
        self._session_id = None
        self.__csrf = None


class SpallocClient:
    """
    Basic client library for talking to new Spalloc.
    """
    __slots__ = ("__session",
                 "__machines_url", "__jobs_url", "version")

    def __init__(self, service_url, username=None, password=None):
        """
        :param str service_url: The reference to the service.
            May have username and password supplied as part of the network
            location; if so, the ``username`` and ``password`` arguments
            *must* be ``None``.
        :param str username: The user name to use
        :param str password: The password to use
        """
        if username is None and password is None:
            service_url, username, password = self.__parse_service_url(
                service_url)
        self.__session = _Session(service_url, username, password)
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

    def launch_keepalive_task(self, job):
        """
        Starts a periodic task to keep a job alive.

        Tricky! *Cannot* be done with a thread, as the main thread is known
        to do significant amounts of CPU-intensive work.

        :param SpallocJob job:
            The job to keep alive
        :return:
            Some kind of closeable task handle; closing it terminates the task.
            Destroying the job will also terminate the task.
        """
        term_queue = Queue(1)

        class Closer:
            def close(self):
                term_queue.put("quit")

        closer = Closer()
        job._keepalive_handle = closer
        cookies, headers = self.__session._credentials
        p = Process(target=_SpallocKeepalive, args=(
            job._keepalive_url, cookies, headers, 30, term_queue), daemon=True)
        p.start()
        return closer

    def close(self):
        if self.__session is not None:
            self.__session._purge()
        self.__session = None

    def __enter__(self):
        """
        :rtype: SpallocClient
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def _SpallocKeepalive(url, cookies, headers, interval, term_queue):
    headers["Content-Type"] = "text/plain; charset=UTF-8"
    while True:
        requests.put(url, data="alive", cookies=cookies, headers=headers,
                     allow_redirects=False)
        try:
            term_queue.get(True, interval)
            break
        except Empty:
            continue


class SpallocMachine:
    """
    Represents a spalloc-controlled machine.

    Don't make this yourself. Use :py:class:`SpallocClient` instead.
    """
    __slots__ = ("__session", "__url",
                 "name", "tags", "width", "height",
                 "dead_boards", "dead_links")

    def __init__(self, session, machine_data):
        """
        :param _Session session:
        :param dict machine_data:
        """
        self.__session = session
        #: The name of the machine.
        self.name = machine_data["name"]
        #: The tags of the machine.
        self.tags = frozenset(machine_data["tags"])
        self.__url = _clean_url(machine_data["uri"])
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


class SpallocJob:
    """
    Represents a job in spalloc.

    Don't make this yourself. Use :py:class:`SpallocClient` instead.
    """
    __slots__ = ("__session", "__url", "__machine_url", "__chip_url",
                 "_keepalive_url", "__keepalive_handle")

    def __init__(self, session, job_handle):
        """
        :param _Session session:
        :param str job_handle:
        """
        logger.info("established job at {}", job_handle)
        self.__session = session
        self.__url = _clean_url(job_handle)
        self.__machine_url = self.__url + "machine"
        self.__chip_url = self.__url + "chip"
        self._keepalive_url = self.__url + "keepalive"
        self.__keepalive_handle = None

    def get_state(self):
        """
        Get the current state of the machine.

        :rtype: SpallocState
        """
        obj = self.__session.get(self.__url).json()
        return SpallocState[obj["state"]]

    def get_root_host(self):
        """
        Get the IP address for talking to the machine.

        :return: The IP address, or ``None`` if not allocated.
        :rtype: str or None
        """
        r = self.__session.get(self.__machine_url)
        if r.status_code == 204:
            return None
        obj = r.json()
        for c in obj["connections"]:
            [x, y], host = c
            if x == 0 and y == 0:
                return host
        return None

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
            obj = self.__session.get(self.__url, wait="true").json()
            s = SpallocState[obj["state"]]
            if s != old_state or s == SpallocState.DESTROYED:
                return s

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
        self.__session.delete(self.__url, reason=reason)
        logger.info("deleted job at {}", self.__url)

    def keepalive(self):
        """
        Signal the job that we want it to stay alive for a while longer.
        """
        self.__session.put(self._keepalive_url, "alive")

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
        r = self.__session.get(self.__chip_url, x=int(x), y=int(y))
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
        return f"SpallocJob({self.__url})"


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
