from spinnman import constants as spinnman_constants


class FrontEndCommonTagsLoader(object):
    """ Loads tags onto the machine
    """

    def __call__(
            self, transceiver, tags=None, iptags=None, reverse_iptags=None):
        """
        :param tags: the tags object which contains ip and reverse ip tags.
                    could be none if these are being given in seperate lists
        :param iptags: a lsit of iptags, gvien when tags is none
        :param reverse_iptags: a list of reverse iptags when tags is none.
        :param transceiver: the transceiver object

        :return none
        """
        # clear all the tags from the ethernet connection, as nothing should
        # be allowed to use it (no two sims should use the same etiehrnet
        # connection at the same time
        for tag_id in range(spinnman_constants.MAX_TAG_ID):
            transceiver.clear_ip_tag(tag_id)

        if tags is not None:
            self.load_iptags(tags.ip_tags, transceiver)
            self.load_reverse_iptags(tags.reverse_ip_tags, transceiver)
        else:
            self.load_iptags(iptags, transceiver)
            self.load_reverse_iptags(reverse_iptags, transceiver)

        return {"LoadedIPTagsToken": True, "LoadedReverseIPTagsToken": True}

    @staticmethod
    def load_iptags(iptags, transciever):
        """
        loads all the iptags individually.
        :param iptags: the iptags to be loaded.
        :param transciever: the transciever object
        :return: none
        """
        for ip_tag in iptags:
            transciever.set_ip_tag(ip_tag)

    @staticmethod
    def load_reverse_iptags(reverse_ip_tags, transciever):
        """
        loads all the reverse iptags individually.
        :param reverse_ip_tags: the reverse iptags to be loaded
        :param transciever: the transciever object
        :return: None
        """
        for reverse_ip_tag in reverse_ip_tags:
            transciever.set_reverse_ip_tag(reverse_ip_tag)
