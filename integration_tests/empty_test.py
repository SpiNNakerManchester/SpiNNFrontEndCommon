import unittest


class EmptyTest(unittest.TestCase):
    @unittest.skip("empty")
    def test_empty(self):
        pass
