from enum import Enum


class ReinjectorSCPCommands(Enum):
    """ SCP Command codes for reinjection
    """
    SET_ROUTER_TIMEOUT = 0
    SET_ROUTER_EMERGENCY_TIMEOUT = 1
    SET_PACKET_TYPES = 2
    GET_STATUS = 3
    RESET_COUNTERS = 4
    EXIT = 5
    CLEAR = 6
