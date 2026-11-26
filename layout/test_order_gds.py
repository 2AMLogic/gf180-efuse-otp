"""Exercise record-order drift with two serializations of the same cell."""

import struct
import unittest

from order_gds import order_boundaries


def record(kind, payload=b""):
    return struct.pack(">HH", 4 + len(payload), kind) + payload


def boundary(x, property_value):
    ring = (x, 0, x, 10, x + 10, 10, x + 10, 0, x, 0)
    return b"".join((
        record(0x0800), record(0x0D02, b"\x00\x21"), record(0x0E02, b"\x00\x00"),
        record(0x1003, struct.pack(">10i", *ring)),
        record(0x2B02, b"\x00\x01"), record(0x2C06, property_value), record(0x1100),
    ))


class BoundaryOrderTests(unittest.TestCase):
    def test_permutations_preserve_whole_elements_and_cell_boundaries(self):
        a, b = boundary(0, b"aa"), boundary(20, b"bb")
        end_cell = record(0x0700)
        next_cell = record(0x0502, bytes(24)) + record(0x0606, b"c2")
        suffix = end_cell + next_cell + b + end_cell
        expected = a + a + b + suffix
        self.assertEqual(order_boundaries(b + a + a + suffix), expected)
        self.assertEqual(order_boundaries(expected), expected)
        self.assertNotEqual(order_boundaries(b + a + boundary(1, b"aa") + suffix), expected)
