from spinn_front_end_common.abstract_models.\
    abstract_generates_data_specification import \
    AbstractGeneratesDataSpecification
from spinn_front_end_common.abstract_models.\
    abstract_has_associated_binary import \
    AbstractHasAssociatedBinary

from pacman.executor.injection_decorator import \
    supports_injection, inject

import hashlib
import tempfile
import os
import threading

# used to stop file conflicts
_lock_condition = threading.Condition()


@supports_injection
class DataSpecableVertex(
        AbstractGeneratesDataSpecification, AbstractHasAssociatedBinary):

    def __init__(self):
        AbstractGeneratesDataSpecification.__init__(self)
        AbstractHasAssociatedBinary.__init__(self)
        self._no_machine_time_steps = None

