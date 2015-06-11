from pacman.model.constraints.key_allocator_constraints.\
    key_allocator_fixed_mask_constraint import KeyAllocatorFixedMaskConstraint
from pacman.model.constraints.key_allocator_constraints.\
    key_allocator_fixed_key_and_mask_constraint \
    import KeyAllocatorFixedKeyAndMaskConstraint
from pacman.model.routing_info.key_and_mask import KeyAndMask
from pacman.model.partitioned_graph.multi_cast_partitioned_edge \
    import MultiCastPartitionedEdge

from spinn_front_end_common.utilities import exceptions


class CommandPartitionedEdge(MultiCastPartitionedEdge):
    """ An edge from a command sender to a partitioned vertex which is to \
        receive the commands
    """

    def __init__(self, pre_subvertex, post_subvertex, commands):
        MultiCastPartitionedEdge.__init__(self, pre_subvertex, post_subvertex)

        # Go through the commands
        command_keys = dict()
        command_mask = 0
        for command in commands:

            if command.key not in command_keys:

                # If this command has not been seen before, add it
                command_keys[command.key] = command.mask
            else:

                # Otherwise merge the current key mask with the current mask
                command_keys[command.key] = (command_keys[command.key] |
                                             command.mask)

            # Keep track of the masks on all the commands
            command_mask |= command.mask

        if command_mask != 0xFFFFFFFF:

            # If the final command mask contains don't cares, use this as a
            # fixed mask
            self._constraints.append(
                KeyAllocatorFixedMaskConstraint(command_mask))
        else:

            # If there is no mask consensus, check that all the masks are
            # actually 0xFFFFFFFF, as otherwise it will not be possible
            # to assign keys to the edge
            for (key, mask) in command_keys:
                if mask != 0xFFFFFFFF:
                    raise exceptions.ConfigurationException(
                        "Command masks are too different to make a mask"
                        " consistent with all the keys.  This can be resolved"
                        " by either specifying a consistent mask, or by using"
                        " the mask 0xFFFFFFFF and providing exact keys")

            # If the keys are all fixed keys, keep them
            self._constraints.append(
                KeyAllocatorFixedKeyAndMaskConstraint(
                    [KeyAndMask(key, mask) for (key, mask) in command_keys]))
