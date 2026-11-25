#!/usr/bin/env python3
"""Self-test for the break-even interpolation: python3 -I sim/sense-breakeven/test_summarize.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import summarize  # noqa: E402


class Crossing(unittest.TestCase):
    def test_interpolates(self):
        be, _ = summarize.crossing([(300, -0.02), (340, -0.01), (380, 0.01), (420, 0.03)])
        self.assertAlmostEqual(be, 360.0)

    def test_no_sign_change_is_not_extrapolated(self):
        self.assertIsNone(summarize.crossing([(300, 0.01), (340, 0.02)])[0])

    def test_two_sign_changes_refused(self):
        self.assertIsNone(summarize.crossing([(300, -1), (340, 1), (380, -1)])[0])

    def test_missing_value(self):
        self.assertIsNone(summarize.crossing([(300, None), (340, 1)])[0])


if __name__ == "__main__":
    unittest.main()
