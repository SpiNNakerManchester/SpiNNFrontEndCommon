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
import enum
import logging
import multiprocessing
from packaging.version import Version
import queue
import re
import requests
from spinn_utilities.log import FormatAdapter

logger = FormatAdapter(logging.getLogger(__name__))

_S = "JSESSIONID"


class SpallocClient:
    def __init__(self, service_url, username, password):
        """
        :param str service_url:
        :param str username:
        :param str password:
        """
        # pylint: disable=abstract-class-instantiated
        self.__url = service_url
        # TODO better way of building these URLs
        self.__login_form_url = self.__url + "system/login.html"
        self.__login_submit_url = self.__url + "system/perform_login"
        self.__srv_base = self.__url + "srv/spalloc/"
        self.__username = username
        self.__password = password
        self._renew()
        logger.info("established session to {} for {}", service_url, username)

    def _get(self, url, **kwargs):
        while True:
            cookies = {_S: self.__session_id}
            params = kwargs if kwargs else None
            r = requests.get(url, params=params, cookies=cookies,
                             allow_redirects=False)
            logger.debug("GET {} returned {}", url, r.status_code)
            if _S in r.cookies:
                self.__session_id = r.cookies[_S]
            if r.status_code != 401:
                break
            self._renew()
        return r

    def _post(self, url, jsonobj):
        while True:
            cookies = {_S: self.__session_id}
            headers = {self.__csrf_header: self.__csrf}
            r = requests.post(url, json=jsonobj, cookies=cookies,
                              headers=headers, allow_redirects=False)
            logger.debug("POST {} returned {}", url, r.status_code)
            if _S in r.cookies:
                self.__session_id = r.cookies[_S]
            if r.status_code != 401:
                break
            self._renew()
        return r

    def _put(self, url, data):
        while True:
            cookies = {_S: self.__session_id}
            headers = {self.__csrf_header: self.__csrf}
            r = requests.put(url, data=data, cookies=cookies,
                             headers=headers, allow_redirects=False)
            logger.debug("PUT {} returned {}", url, r.status_code)
            if _S in r.cookies:
                self.__session_id = r.cookies[_S]
            if r.status_code != 401:
                break
            self._renew()
        return r

    def _delete(self, url, **kwargs):
        while True:
            params = kwargs if kwargs else None
            cookies = {_S: self.__session_id}
            headers = {self.__csrf_header: self.__csrf}
            r = requests.delete(url, params=params, cookies=cookies,
                                headers=headers, allow_redirects=False)
            logger.debug("DELETE {} returned {}", url, r.status_code)
            if _S in r.cookies:
                self.__session_id = r.cookies[_S]
            if r.status_code != 401:
                break
            self._renew()
        return r

    def _renew(self):
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
        self.__session_id = r.cookies[_S]
        # We don't need to follow that redirect

        # Step three: get the basic service data and new CSRF token
        r = self._get(self.__srv_base)
        logger.debug("GET {} returned {}", self.__srv_base, r.status_code)
        obj = r.json()
        v = obj["version"]
        self.version = Version(
            f"{v['major-version']}.{v['minor-version']}.{v['revision']}")
        self.__csrf_header = obj["csrf-header"]
        self.__csrf = obj["csrf-token"]
        self.__machines_url = obj["machines-ref"]
        self.__jobs_url = obj["jobs-ref"]

    def list_machines(self):
        """
        :rtype: dict(str,SpallocMachine)
        """
        obj = self._get(self.__machines_url).json()
        return {m["name"]: SpallocMachine(self, m) for m in obj["machines"]}

    def create_job(self, num_boards, machine_name=None, keepalive=45):
        """
        :rtype: SpallocJob
        """
        create = {
            "dimensions": [int(num_boards)],
            "keepaliveInterval": f"PT{int(keepalive)}S"
        }
        if machine_name:
            create["machine-name"] = machine_name
        else:
            create["tags"] = ["default"]
        r = self._post(self.__jobs_url, create)
        url = r.headers["Location"]
        return SpallocJob(self, url)

    def launch_keepalive_task(self, job):
        """
        Starts a periodic task to keep a job alive.

        Tricky! *Cannot* be done with a thread, as the main thread is known
        to do significant amounts of CPU-intensive work.

        :param SpallocJob job:
        :return:
            Some kind of closeable task handle; closing it terminates the task.
        """
        term_queue = multiprocessing.Queue(1)

        class Closer:
            def close(self):
                term_queue.put("quit")

        closer = Closer()
        job._keepalive_handle = closer
        cookies = {_S: self.__session_id}
        headers = {self.__csrf_header: self.__csrf}
        p = multiprocessing.Process(target=_SpallocKeepalive, args=(
            job._keepalive_url, cookies, headers, 30, term_queue), daemon=True)
        p.start()
        return closer


def _SpallocKeepalive(url, cookies, headers, interval, term_queue):
    while True:
        requests.put(url, data="alive", cookies=cookies, headers=headers,
                     allow_redirect=False)
        try:
            term_queue.get(True, interval)
            break
        except queue.Empty:
            continue


class SpallocMachine:
    """
    Represents a spalloc-controlled machine.

    Don't make this yourself. Use :py:class:`SpallocClient` instead.
    """

    def __init__(self, client, machine_data):
        """
        :param SpallocClient client:
        :param dict machine_data:
        """
        self.__client = client
        self.name = machine_data["name"]
        self.tags = frozenset(machine_data["tags"])
        self.__url = machine_data["uri"]
        self.width = machine_data["width"]
        self.height = machine_data["height"]
        self.dead_boards = machine_data["dead-boards"]
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

    def __init__(self, client, job_handle):
        """
        :param SpallocClient client:
        :param job_handle:
        """
        logger.info("established job at {}", job_handle)
        self.__client = client
        self.__url = job_handle
        self.__machine_url = job_handle + "/machine"
        self._keepalive_url = job_handle + "/keepalive"
        self.__keepalive_handle = None

    def get_state(self):
        """
        :rtype: SpallocState
        """
        obj = self.__client._get(self.__url).json()
        # TODO check if states are reported by name!
        return SpallocState(obj["state"])

    def get_root_host(self):
        """
        :rtype: str
        """
        r = self.__client._get(self.__machine_url)
        if r.status_code == 204:
            return None
        obj = r.json()
        for c in obj["connections"]:
            x, y, z = c["chip"]
            if x == 0 and y == 0 and z == 0:
                return c["hostname"]
        raise Exception(f"could not parse {obj} to get root chip address")

    def wait_for_state_change(self, old_state):
        """
        :param SpallocState old_state:
        :rtype: SpallocState
        """
        while True:
            obj = self.__client._get(self.__url, wait="true").json()
            s = SpallocState(obj["state"])
            if s != old_state or s == SpallocState.DESTROYED:
                return s

    def destroy(self, reason="finished"):
        """
        :param str reason:
        """
        if self.__keepalive_handle:
            self.__keepalive_handle.close()
            self.__keepalive_handle = None
        self.__client._delete(self.__url, reason=reason)
        logger.info("deleted job at {}", self.__url)

    def keepalive(self):
        self.__client._put(self._keepalive_url, "alive")

    @property
    def _keepalive_handle(self):
        return self.__keepalive_handle

    @_keepalive_handle.setter
    def _keepalive_handle(self, handle):
        if self.__keepalive_handle is not None:
            raise Exception("cannot keep job alive from two tasks")
        self.__keepalive_handle = handle


class SpallocState(enum.IntEnum):
    UNKNOWN = 0
    QUEUED = 1
    POWER = 2
    READY = 3
    DESTROYED = 4
