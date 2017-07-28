from spinn_utilities.progress_bar import ProgressBar
from spinnman.constants import MAX_TAG_ID


class TagsLoader(object):
    """ Loads tags onto the machine
    """

    __slots__ = []

    def __call__(
            self, transceiver, tags=None, iptags=None, reverse_iptags=None):
        """
        :param tags: the tags object which contains ip and reverse ip tags.
                    could be none if these are being given in separate lists
        :param iptags: a list of iptags, given when tags is none
        :param reverse_iptags: a list of reverse iptags when tags is none.
        :param transceiver: the transceiver object
        """
        # clear all the tags from the Ethernet connection, as nothing should
        # be allowed to use it (no two apps should use the same Ethernet
        # connection at the same time
        progress = ProgressBar(MAX_TAG_ID, "Clearing tags")

        for tag_id in progress.over(range(MAX_TAG_ID)):
            transceiver.clear_ip_tag(tag_id)

        progress = None
        if tags is not None:
            progress = ProgressBar(
                len(list(tags.ip_tags)) + len(list(tags.reverse_ip_tags)),
                "Loading Tags")
            self.load_iptags(tags.ip_tags, transceiver, progress)
            self.load_reverse_iptags(
                tags.reverse_ip_tags, transceiver, progress)
        else:
            progress = ProgressBar(
                len(iptags) + len(reverse_iptags),
                "Loading Tags")
            self.load_iptags(iptags, transceiver, progress)
            self.load_reverse_iptags(reverse_iptags, transceiver, progress)
        progress.end()

        return True, True

    @staticmethod
    def load_iptags(iptags, transceiver, progress_bar):
        """ Loads all the iptags individually.

        :param iptags: the iptags to be loaded.
        :param transceiver: the transceiver object
        :rtype: None
        """
        for ip_tag in iptags:
            transceiver.set_ip_tag(ip_tag)
            progress_bar.update()

    @staticmethod
    def load_reverse_iptags(reverse_ip_tags, transceiver, progress_bar):
        """ Loads all the reverse iptags individually.

        :param reverse_ip_tags: the reverse iptags to be loaded
        :param transceiver: the transceiver object
        :rtype: None
        """
        for reverse_ip_tag in reverse_ip_tags:
            transceiver.set_reverse_ip_tag(reverse_ip_tag)
            progress_bar.update()
