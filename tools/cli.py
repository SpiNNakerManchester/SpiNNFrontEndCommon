from tools.pybug import BadArgs


class CLI(object):
    def __init__(self, channel, prompt, commands, term):
        self.channel = channel
        self.prompt = prompt
        self.commands = dict(commands)
        self.term = term
        self.level = 0
        self.quiet = 0
        self.tty = channel.isatty()
        self.__args = []

    @property
    def state(self):
        return (
            self.channel, self.tty, self.prompt, self.quiet,
            self.term, self.level, self.commands)

    @state.setter
    def state(self, state):
        (self.channel, self.tty, self.prompt, self.quiet, self.term,
         self.level, self.commands) = state

    def cmd(self, command_set, delete=False):
        """ update command list """
        if delete:
            self.commands = dict()
        self.commands.update(command_set)

    def run(self):
        """ execute a CLI """
        # FIXME

    def pause(self):
        text = " ".join(self.__args).replace(r"\n", "\n")
        print(text)
        input()

    @property
    def count(self):
        return len(self.__args)

    @property
    def args(self):
        for a in self.__args:
            yield a

    def arg(self, n):
        return self.__args[n]


def Pause(cli):
    """ print a string and wait for Enter key """
    text = " ".join(cli.args).replace(r"\n", "\n")
    print(text)
    input()


def Echo(cli):
    """ print a string """
    text = " ".join(cli.args).replace(r"\n", "\n")
    print(text)


def Quit(cli):
    if cli.count:
        raise BadArgs
    return 1


def Help(cli):
    """ command to print help information on CLI commands """
    if cli.count == 1:
        cmd = cli.arg(0)
        info = cli.commands.get(cmd, None)
        if info is not None:
            print("usage:   {} {}".format(cmd, info[1]))
            print("purpose: {}".format(info[2]))
            return
    elif cli.count:
        raise BadArgs

    cmds = list(cli.commands)
    cmds.sort()
    for cmd in cmds:
        info = cli.commands[cmd]
        print(" {:-12s} {:-30s} - {}".format(cmd, info[1], info[2]))


def At(cli):
    """ command to read CLI commands from a file """
    if not 1 <= cli.count <= 2:
        raise BadArgs
    filename = cli.arg(0)
    _quiet = 0 if cli.count == 1 else int(cli.arg(1))
    if cli.level > 10:
        raise RuntimeError("@ nested too deep")

    with open(filename) as fh:
        state = cli.state

        cli.level += 1
        cli.channel = fh
        cli.tty = fh.isatty()
        cli.prompt = "@" + cli.prompt
        cli.quiet = _quiet
        cli.term = None
        try:
            cli.run()
        finally:
            cli.state = state


def Query(cli):
    """ command to print a list of CLI commands """
    cmds = list(cli.commands)
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
