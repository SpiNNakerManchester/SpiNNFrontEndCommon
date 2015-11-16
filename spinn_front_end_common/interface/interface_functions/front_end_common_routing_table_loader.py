from pacman.utilities.utility_objs.progress_bar import ProgressBar


class FrontEndCommonRoutingTableLoader(object):

    def __call__(self, router_tables, app_id, transciever, machine):
        progress_bar = ProgressBar(len(list(router_tables.routing_tables)),
                                   "Loading routing data onto the machine")

        # load each router table that is needed for the application to run into
        # the chips sdram
        for router_table in router_tables.routing_tables:
            if not machine.get_chip_at(router_table.x, router_table.y).virtual:
                transciever.clear_multicast_routes(router_table.x,
                                                   router_table.y)
                transciever.clear_router_diagnostic_counters(router_table.x,
                                                             router_table.y)

                if len(router_table.multicast_routing_entries) > 0:
                    transciever.load_multicast_routes(
                        router_table.x, router_table.y,
                        router_table.multicast_routing_entries, app_id=app_id)
            progress_bar.update()
        progress_bar.end()

        return {"LoadedRoutingTablesToken": True}