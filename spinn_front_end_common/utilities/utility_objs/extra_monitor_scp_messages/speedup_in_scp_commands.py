from enum import Enum


class SpeedupInSCPCommands(Enum):
    """ SCP Command codes for data speed up in
    """
    READ_APPLICATION_ROUTING_TABLE = 6,
    LOAD_APPLICATION_MC_ROUTES = 7,
    LOAD_SYSTEM_MC_ROUTES = 8
