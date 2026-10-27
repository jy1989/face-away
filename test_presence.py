import unittest

from presence import PresenceGate


class PresenceTests(unittest.TestCase):
    def test_debounce_and_restore(self):
        gate = PresenceGate(away_seconds=3, return_seconds=1)
        self.assertIsNone(gate.observe(True, 0.0))
        self.assertIsNone(gate.observe(False, 1.0))
        self.assertIsNone(gate.observe(False, 3.9))
        self.assertEqual(gate.observe(False, 4.1), "hide")
        self.assertTrue(gate.hidden)
        self.assertIsNone(gate.observe(True, 4.2))
        self.assertIsNone(gate.observe(False, 4.4))
        self.assertIsNone(gate.observe(True, 5.0))
        self.assertEqual(gate.observe(True, 6.1), "restore")
        self.assertFalse(gate.hidden)

    def test_short_absence_no_hide(self):
        gate = PresenceGate(away_seconds=3)
        self.assertIsNone(gate.observe(False, 0))
        self.assertIsNone(gate.observe(True, 2))
        self.assertIsNone(gate.observe(False, 4))
        self.assertIsNone(gate.observe(False, 6.9))

    def test_reset(self):
        gate = PresenceGate(away_seconds=1)
        gate.observe(False, 0)
        self.assertEqual(gate.observe(False, 2), "hide")
        gate.reset()
        self.assertFalse(gate.hidden)
        self.assertIsNone(gate.observe(True, 3))


if __name__ == "__main__":
    unittest.main()
