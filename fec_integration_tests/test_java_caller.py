import unittest

from spinn_front_end_common.interface.java_caller import JavaCaller


class TestJavaCaller(unittest.TestCase):

    def test_creation(self):
        caller = JavaCaller("java")