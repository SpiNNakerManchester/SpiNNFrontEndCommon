"""
helper functions for converting a key
"""

# TODO Should this even exist anymore. given the virtual key space?

# define key_x(k) (k >> 24)
# define key_y(k) ((k >> 16) & 0xFF)
# define key_p(k) ((k >> 11) & 0xF)
# define nid(k) (k & 0x8FF)

# basic key to coordinates converters
def get_x_from_key(key):
    """

    :param key:
    :return:
    """
    return key >> 24


def get_y_from_key(key):
    """

    :param key:
    :return:
    """
    return (key >> 16) & 0xFF


def get_p_from_key(key):
    """

    :param key:
    :return:
    """
    return (key >> 11) & 0x1F


def get_nid_from_key(key):
    """

    :param key:
    :return:
    """
    return key & 0x7FF


def get_key_from_coords(chipX, chipY, chipP):
    """

    :param chipX:
    :param chipY:
    :param chipP:
    :return:
    """
    return chipX << 24 | chipY << 16 | chipP << 11


def get_mpt_sb_mem_addrs_from_coords(x, y, p):
    """

    :param x:
    :param y:
    :param p:
    :return:
    """
    # two bytes per entry
    return (p + (18 * y) + (18 * 8 * x)) * 2
