

class ProvenanceDataItems(object):
    """
    ProvenanceDataItems: container for provenance data items
    """

    def __init__(self):
        self._items_by_location = dict()
        self._items_by_operation = dict()

    def add_provenance_item_by_location(self, placement, prov_items):
        """
        adds items to prov from a given placement
        :param placement: the placement associated with these prov items
        :param prov_items: the prov items
        :return:
        """
        if placement not in self._items_by_location:
            self._items_by_location[placement] = list()
        if hasattr(prov_items, '__iter__'):
            for item in prov_items:
                self._items_by_location[placement].append(item)
        else:
            self._items_by_location[placement].append(prov_items)

    def add_provenance_item_by_operation(self, operation_id, prov_items):
        """

        :param operation_id: the id for the operation
        :param prov_items: the prov items associated with that operation
        :return:
        """
        if operation_id not in self._items_by_operation:
            self._items_by_operation[operation_id] = list()
        if hasattr(prov_items, '__iter__'):
            for item in prov_items:
                self._items_by_operation[operation_id].append(item)
        else:
            self._items_by_operation[operation_id].append(prov_items)

    def get_prov_items_for_placement(self, placement):
        """
        returns the prov items by placement
        :param placement: the placement to find prov items with
        :return: the prov items or None
        """
        if placement not in self._items_by_location:
            return None
        else:
            return self._items_by_location[placement]

    def get_placements_which_have_provenance_data(self):
        """
        returns the list of placements which have provenance data
        :return: iterable of placement
        """
        return self._items_by_location.keys()

    def get_prov_items_for_operation(self, operation_id):
        """
        get prov items from a operation id
        :param operation_id: the operation id to find prov items for
        :return: the prov items or None
        """
        if operation_id not in self._items_by_operation:
            return None
        else:
            return self._items_by_operation[operation_id]

    def get_operation_ids(self):
        """
        returns the operations stored in this provenance data store
        :return: list of operation ids
        """
        return self._items_by_operation.keys()