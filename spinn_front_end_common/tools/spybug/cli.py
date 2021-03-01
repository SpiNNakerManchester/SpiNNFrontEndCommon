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
    """ Basic support code for an interactive command line interface.

    **Standard commands:**

    ``pause <string>``
        Print string and wait for Enter key
    ``echo <string>``
        Print string
    ``quit``
        Terminate
    ``help [<command>]``
        Print help, either general or on a specific command
    ``@ <filename> [quiet]``
        Read commands from a file
    ``?``
        List available commands
    """
    def __init__(self, channel, prompt, commands):
        """
        :param channel:
            Where to read commands from.
        :param str prompt:
            The prompt to display
        :param commands:
            The set of commands to install; each command has its name as its
            key, and a tuple as value containing the implementation, a
            description of the arguments accepted, and some help text. The
            implementation will get passed a copy of this object when called,
            which it can use to get the arguments that were passed.
        :type commands:
            dict(str,tuple(~collections.abc.Callable[[CLI],None],str,str))
        """
        self._channel = channel
        self._prompt = prompt
        self._commands = {}
        self.cmd(commands, delete=True)
        self._term = readline
        self._level = 0
        self._quiet = 0
        self._tty = channel.isatty()
        self._args = []

    @property
    def prompt(self):
        """ The prompt to display; settable

        :rtype: str
        """
        return self._prompt

    @prompt.setter
    def prompt(self, value):
        self._prompt = str(value)

    @property
    def state(self):
        """ The state of the CLI, so it can be saved and restored.

        There is no guarantee that any state can be set other than one read
        from this object.
        """
        return (
            self._channel, self._tty, self.prompt, self._quiet,
            self._term, self._level, self._commands)

    @state.setter
    def state(self, state):
        (self._channel, self._tty, self.prompt, self._quiet, self._term,
         self._level, self._commands) = state

    def cmd(self, command_set, *, delete=False):
        """ Update the command list

        :param command_set:
            The commands to add; each command has its name as its key, and
            a tuple as value containing the implementation, a description
            of the arguments accepted, and some help text. The
            implementation will get passed a copy of this object when it is
            called, which it can use to get the arguments that were passed.
        :type command_set:
            dict(str,tuple(~collections.abc.Callable[[CLI],None],str,str))
        :keyword bool delete:
            Whether to reset the existing commands to default first.
        """
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
        """ The commands whose names start with a given prefix.

        :param str string: The prefix
        :rtype: ~collections.abc.Iterable(str)
        """
        for c in self._commands:
            if c.startswith(string):
                yield c

    def __prompt(self):
        if self._tty and self._term is None:
            print(self.prompt, end="", flush=True)

    def run(self):
        """
        Execute a CLI; the commands are those installed in the command set.
        Lines starting with ``#`` (after spaces are stripped) are comments.
        """
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
                    print(f"error: {e}")
            else:
                print(f'bad command "{cmd}"')
            self.__prompt()

    def __write(self, text):
        print(text, flush=self._tty)

    @property
    def count(self):
        """ The number of arguments in the current command.

        :rtype: int
        """
        return len(self._args)

    @property
    def args(self):
        """ The arguments in the current command.

        :rtype: ~collections.abc.Iterable(str)
        """
        yield from self._args

    def arg(self, n):
        """ Get the *n*'th argument

        :param int n:
        :rtype: str
        """
        return self._args[n]

    def arg_i(self, n):
        """ Get the *n*'th argument as an integer

        :param int n:
        :rtype: int
        """
        return int(self._args[n], base=0)

    def arg_x(self, n):
        """ Get the *n*'th argument as a hexadecimal integer

        :param int n:
        :rtype: int
        """
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
                print(f"usage:   {cmd} {info[1]}")
                print(f"purpose: {info[2]}")
                return
        elif self.count:
            raise BadArgs

        cmds = list(self._commands)
        cmds.sort()
        for cmd in cmds:
            info = self._commands[cmd]
            print(f" {cmd:<12s} {info[1]:<30s} - {info[2]}")

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
