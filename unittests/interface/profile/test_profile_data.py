import unittest
import struct
from spinn_front_end_common.interface.profiling.profile_data import ProfileData

_ENTER_TAG = 0x80000000
_EXIT_TAG = 0x00000000
_CLOCK_PER_MS = 200000
_CLOCK_MAX = (2**32) - 1


def _get_clock(timestep, ms_into_timestep):
    return _CLOCK_MAX - int((timestep + ms_into_timestep) * _CLOCK_PER_MS)


class Test(unittest.TestCase):

    def test_use(self):

        # Set up the object to test
        profile_data = ProfileData({3: "Test", 4: "Test2"})

        # Create some samples
        samples = [
            _get_clock(1, 0), _ENTER_TAG | 3,
            _get_clock(1, 0.1), _ENTER_TAG | 4,
            _get_clock(1, 0.2), _EXIT_TAG | 3,
            _get_clock(1, 0.4), _EXIT_TAG | 4,
            _get_clock(2, 0.1), _ENTER_TAG | 4,
            _get_clock(2, 0.4), _EXIT_TAG | 4,
        ]
        data = bytearray(struct.pack("<{}I".format(len(samples)), *samples))

        # Read back the data
        profile_data.add_data(data)

        # Should be 2 tags as 2 specified
        self.assertEqual(len(profile_data.tags), 2)

        # Should be 0.2ms between "Test" tag start and end, as only one
        self.assertEqual(profile_data.get_mean_ms("Test"), 0.2)

        # Should be 1 call in total of "Test" tag
        self.assertEqual(profile_data.get_n_calls("Test"), 1)

        # Should be 0.5 calls per time step of "Test" tag
        # (as 2 timesteps at 1ms)
        self.assertEqual(
            profile_data.get_mean_n_calls_per_ts("Test", 0, 1.0), 0.5)

        # Should be 0.1ms per time step of "Test" tag (as 2 timesteps of 1ms)
        self.assertEqual(
            profile_data.get_mean_ms_per_ts("Test", 0, 1.0), 0.1)

        # Should be 0.3ms on average between "Test2" start tag and end as
        # 2 and both the same difference between start and end
        self.assertAlmostEqual(profile_data.get_mean_ms("Test2"), 0.3)

        # Should be 2 calls in total of "Test2" tag
        self.assertEqual(profile_data.get_n_calls("Test2"), 2)

        # Should be 1 per time step of "Test2" tag
        self.assertEqual(
            profile_data.get_mean_n_calls_per_ts("Test2", 0, 1.0), 1)

        # Should be 0.3ms on average per time step for "Test2" tag
        self.assertAlmostEqual(
            profile_data.get_mean_ms_per_ts("Test2", 0, 1.0), 0.3)


if __name__ == "__main__":
    unittest.main()
