"""
general reload script - note that imports are required so don't remove them!
"""

# pacman imports
from pacman.model.placements.placements import Placements
from pacman.model.placements.placement import Placement
from pacman.model.routing_info.routing_info import RoutingInfo
from pacman.model.routing_info.subedge_routing_info import SubedgeRoutingInfo
from pacman.model.routing_tables.multicast_routing_tables import \
    MulticastRoutingTables
from pacman.model.tags.tags import Tags

# spinnman imports
from spinnman.model.core_subsets import CoreSubsets
from spinnman.model.core_subset import CoreSubset

# spinnmachine imports
from spinn_machine.tags.iptag import IPTag
from spinn_machine.tags.reverse_iptag import ReverseIPTag

# front end common imports
from spinn_front_end_common.utilities.report_states import ReportState
from spinn_front_end_common.utilities.reload.reload import Reload
from spinn_front_end_common.utilities.reload.reload_application_data \
    import ReloadApplicationData
from spinn_front_end_common.utilities.executable_targets \
    import ExecutableTargets
from spinn_front_end_common.utilities.reload.reload_routing_table import \
    ReloadRoutingTable
from spinn_front_end_common.utilities.reload.reload_buffered_vertex import \
    ReloadBufferedVertex
from spinn_front_end_common.utilities.notification_protocol.\
    socket_address import SocketAddress

# general imports
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
for handler in logging.root.handlers:
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)-15s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"))

application_data = list()
binaries = ExecutableTargets()
iptags = list()
reverse_iptags = list()
buffered_tags = Tags()
buffered_placements = Placements()

routing_tables = MulticastRoutingTables()
# database params
socket_addresses = list()

reports_states = ReportState(False, False, False, False, False,
                             False, False, False, False, False)
