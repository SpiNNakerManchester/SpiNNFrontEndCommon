
class FrontEndCommonInsertEdgesToLivePacketGatherers(object):

    def __call__(
            self, live_packet_gatherers, placements,
            live_packet_gatherers_to_vertex_mapping, machine,
            machine_graph, application_graph=None, graph_mapper=None):

        for live_packet_gatherers_param in live_packet_gatherers:
            for vertex_to_connect in live_packet_gatherers[
                    live_packet_gatherers_param]:


