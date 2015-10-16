from spinnman import constants as spinnman_constants


class FrontEndCommonTagsLoader(object):
    """
    FrontEndCommonTagsLoader: loads tags onto the machine
    """

    def __call__(self, tags, transciever):
        """ loads all the tags onto all the boards
        :param tags: the tags object which contains ip and reverse ip tags.
        :param transciever: the transciever object
        :return none
        """
        # clear all the tags from the ethernet connection, as nothing should
        # be allowed to use it (no two sims should use the same etiehrnet
        # connection at the same time
        for tag_id in range(spinnman_constants.MAX_TAG_ID):
            transciever.clear_ip_tag(tag_id)

        self.load_iptags(tags.ip_tags, transciever)
        self.load_reverse_iptags(tags.reverse_ip_tags, transciever)

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
