import os

_REPORT_FILENAME = "tags_on_machine.txt"


class TagsFromMachineReport(object):
    def __call__(self, report_default_directory, transceiver):
        filename = os.path.join(report_default_directory, _REPORT_FILENAME)
        tags = self._get_tags(transceiver)
        with open(filename, "w") as f:
            f.write("Tags actually read off the machine\n")
            f.write("==================================\n")
            for tag in tags:
                f.write("{}\n".format(self._render_tag(tag)))

    def _get_tags(self, txrx):
        try:
            return txrx.get_tags()
        except Exception as e:  # pylint: disable=broad-except
            return [e]

    def _render_tag(self, tag):
        return repr(tag)
