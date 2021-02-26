# Copyright (c) 2013-2020 The University of Manchester
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
import readline
from .exn import BadArgs


class CLI(object):
    def __init__(self, channel, prompt, commands):
        self._channel = channel
        self.prompt = prompt
        self._commands = {}
        self.cmd(commands, True)
        self._term = readline
        self._level = 0
        self._quiet = 0
        self._tty = channel.isatty()
        self._args = []

    @property
    def state(self):
        return (
            self._channel, self._tty, self.prompt, self._quiet,
            self._term, self._level, self._commands)

    @state.setter
    def state(self, state):
        (self._channel, self._tty, self.prompt, self._quiet, self._term,
         self._level, self._commands) = state

    def cmd(self, command_set, delete=False):
        """ update command list """
        if delete:
            self._commands = {
                "pause": (
                    self._cmd_pause,
                    "<text.S>",
                    "Print string and wait for Enter key"),
                "echo": (
                    self._cmd_echo,
                    "<text.S>",
                    "Print string"),
                "quit": (
                    self._cmd_quit,
                    "",
                    "Quit"),
                "help": (
                    self._cmd_help,
                    "",
                    "Provide help"),
                "@": (
                    self._cmd_at,
                    "<file.F> [quiet]",
                    "Read commands from file"),
                "?": (
                    self._cmd_query,
                    "",
                    "List commands"),
            }
        self._commands.update(command_set)

    def commands_starting_with(self, string):
        for c in self._commands:
            if c.startswith(string):
                yield c

    def __prompt(self):
        if self._tty and self._term is None:
            print(self.prompt, end="", flush=True)

    def run(self):
        """ execute a CLI """
        self.__prompt()
        for line in self._channel:
            if not self._tty and not self._quiet:
                print(self.prompt + line)
            print("")
            line = line.strip()
            if not line or line.startswith("#"):
                self.__prompt()
                continue
            self._args = line.split()
            cmd = self._args.pop(0)
            if cmd in self._commands:
                try:
                    if self._commands[cmd][0](self):
                        break
                except Exception as e:  # pylint: disable=broad-except
                    print("error: {}".format(e))
            else:
                print("bad command \"{}\"".format(cmd))
            self.__prompt()

    def __write(self, text):
        print(text, flush=self._tty)

    @property
    def count(self):
        return len(self._args)

    @property
    def args(self):
        for a in self._args:
            yield a

    def arg(self, n):
        return self._args[n]

    def arg_i(self, n):
        return int(self._args[n], base=0)

    def arg_x(self, n):
        return int(self._args[n], base=16)

    # Default commands of a CLI object; always present!

    def _cmd_pause(self):
        """ print a string and wait for Enter key """
        self.__write(" ".join(self.args).replace(r"\n", "\n"))
        self._channel.readline()

    def _cmd_echo(self):
        """ print a string """
        self.__write(" ".join(self.args).replace(r"\n", "\n"))

    def _cmd_quit(self):
        if self.count:
            raise BadArgs
        return 1

    def _cmd_help(self):
        """ command to print help information on CLI commands """
        if self.count == 1:
            cmd = self.arg(0)
            info = self._commands.get(cmd, None)
            if info is not None:
                print("usage:   {} {}".format(cmd, info[1]))
                print("purpose: {}".format(info[2]))
                return
        elif self.count:
            raise BadArgs

        cmds = list(self._commands)
        cmds.sort()
        for cmd in cmds:
            info = self._commands[cmd]
            print(" {:<12s} {:<30s} - {}".format(cmd, info[1], info[2]))

    def _cmd_at(self):
        """ command to read CLI commands from a file """
        if not 1 <= self.count <= 2:
            raise BadArgs
        filename = self.arg(0)
        quiet = 0 if self.count == 1 else self.arg_i(1)
        if self._level > 10:
            raise RuntimeError("@ nested too deep")

        with open(filename) as fh:
            state = self.state

            self._level += 1
            self._channel = fh
            self._tty = fh.isatty()
            self.prompt = "@" + self.prompt
            self._quiet = quiet
            self._term = None
            try:
                self.run()
            finally:
                self.state = state

    def _cmd_query(self):
        """ command to print a list of CLI commands """
        cmds = list(self._commands)
        cmds.sort()
        s = ""
        for cmd in cmds:
            if len(s + " " + cmd) > 78:
                print(s)
                s = ""
            s += " "
            s += cmd
        if s:
            print(s)
