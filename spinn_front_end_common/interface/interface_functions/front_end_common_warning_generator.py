from pacman.interfaces.abstract_provides_provenance_data import \
    AbstractProvidesProvenanceData
from pacman.model.placements.placement import Placement
from pacman.utilities.utility_objs.message_holder import MessageHolder


class FrontEndCommonWarningGenerator(object):
    """
    generator that searches though prov data to locate warnings which need to
    be bought to the end users attention.
    """

    def __call__(self, prov_data_items, placements, router_tables):
        warning_messages = MessageHolder()

        for placement in placements.placements:
            if isinstance(placement.subvertex,
                          AbstractProvidesProvenanceData):
                # write to warnings as needed
                self._add_warnings_as_needed_for_placement(
                    prov_data_items, warning_messages, placement)

        for router_table in router_tables.routing_tables:
            placement = Placement(None, router_table.x, router_table.y, None)
            self._add_warnings_as_needed_for_placement(
                prov_data_items, warning_messages, placement)

        for operation in prov_data_items.get_operation_ids():
            self._add_core_warnings_as_needed_for_operation(
                prov_data_items, warning_messages, operation)

        return {'warning_messages': warning_messages}

    @staticmethod
    def _add_warnings_as_needed_for_placement(
            prov_data_items, warning_messages, placement):
        for item in prov_data_items.get_prov_items_for_placement(placement):
            if item.needs_reporting_to_end_user:
                if placement.p is None:
                    warning_messages.add_chip_message(
                        placement.x, placement.y, item.message_to_end_user)
                else:
                    warning_messages.add_core_message(
                        placement.x, placement.y, placement.p,
                        item.message_to_end_user)

    @staticmethod
    def _add_core_warnings_as_needed_for_operation(
            prov_data_items, warning_messages, operation_id):
        for item in prov_data_items.get_prov_items_for_operation(operation_id):
            if item.needs_reporting_to_end_user:
                warning_messages.add_operation_message(
                    operation_id, item.message_to_end_user)
