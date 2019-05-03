import unittest

from spinn_front_end_common.interface.java_caller import JavaCaller

# This test will not run on travis as there is no Java directory


class TestJavaCaller(unittest.TestCase):

    def test_creation(self):
        caller = JavaCaller("somepath", "java")
        assert caller is not None
