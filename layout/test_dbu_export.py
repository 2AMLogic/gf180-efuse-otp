#!/usr/bin/env python3
"""Unit tests for layout/dbu_export.py, the shared final-write 2:1 coarsen.

`gen_efuse_otp.py` imports `coarsen()` and `layout/pnr.sh` shells out with
`--pin-markers`, but CI never regenerates either committed stream, so a
regression inside the module itself would pass CI unnoticed. These tests
build synthetic in-memory kdb.Layout fixtures at 0.0005 um -- no PDK, no
OpenROAD, no committed stream -- and cover the exact-conversion path, every
odd-coordinate rejection path, the single-pin net marker reconstruction and
the CLI contract of main().

    . signoff/klt.sh && klt_python -I -m unittest discover \
        -s layout -p 'test_dbu_export.py' -v

Run by the harness job of .github/workflows/ci.yml under the pinned
interpreter of signoff/klt-pin.txt. It is deliberately not part of
scripts/ci/check_ci.sh: that script runs under the host python3, which has
no klayout binding, and a missing binding here must fail the step.
"""
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dbu_export  # noqa: E402  (needs the path insert above under -I)
from dbu_export import DbuError  # noqa: E402

import klayout.db as kdb  # noqa: E402

GEOM = (42, 0)   # plain geometry layer of the conversion fixtures
METAL = (34, 0)  # pin-metal layer of the marker fixtures (module is generic)


def new_source():
    """A fresh 0.0005 um layout: TOP referencing an empty CHILD cell."""
    ly = kdb.Layout()
    ly.dbu = dbu_export.SOURCE_DBU_UM
    top = ly.create_cell("TOP")
    child = ly.create_cell("CHILD")
    return ly, top, child


def gds_bytes(layout, directory, name):
    """Deterministic (timestamp-free) GDS bytes, for unmodified-layout proofs."""
    path = os.path.join(directory, name)
    dbu_export.write_gds(layout, path)
    with open(path, "rb") as fh:
        return fh.read()


class EvenConversion(unittest.TestCase):
    """An all-even layout coarsens exactly: the micron geometry is unchanged."""

    def test_shapes_texts_instances_and_array_pitches_halve_exactly(self):
        ly, top, child = new_source()
        li_box = ly.layer(*GEOM)
        li_poly = ly.layer(43, 0)
        li_path = ly.layer(44, 0)
        li_text = ly.layer(45, 0)
        child.shapes(li_box).insert(kdb.Box(0, 0, 100, 100))
        top.shapes(li_box).insert(kdb.Box(0, 0, 200, 100))
        poly = kdb.Polygon([kdb.Point(0, 0), kdb.Point(400, 0),
                            kdb.Point(400, 300), kdb.Point(0, 300)])
        poly.insert_hole([kdb.Point(100, 100), kdb.Point(100, 200),
                          kdb.Point(300, 200), kdb.Point(300, 100)])
        top.shapes(li_poly).insert(poly)
        top.shapes(li_path).insert(kdb.Path([kdb.Point(0, 0),
                                             kdb.Point(500, 0)], 20))
        text = kdb.Text("PAD", kdb.Trans(kdb.Vector(100, 200)))
        text.size = 40
        top.shapes(li_text).insert(text)
        top.insert(kdb.CellInstArray(child.cell_index(),
                                     kdb.Trans(kdb.Vector(1000, 2000))))
        top.insert(kdb.CellInstArray(child.cell_index(),
                                     kdb.Trans(kdb.Vector(1000, 4000)),
                                     kdb.Vector(2000, 0), kdb.Vector(0, 4000),
                                     3, 2))

        rebuilt = dbu_export.coarsen(ly)

        self.assertEqual(rebuilt, [])
        self.assertEqual(ly.dbu, dbu_export.TARGET_DBU_UM)

        boxes = list(top.shapes(li_box).each())
        self.assertEqual(len(boxes), 1)
        box = boxes[0].box
        self.assertEqual((box.left, box.bottom, box.right, box.top),
                         (0, 0, 100, 50))
        self.assertAlmostEqual(box.width() * ly.dbu, 0.1)
        self.assertAlmostEqual(box.height() * ly.dbu, 0.05)

        polys = list(top.shapes(li_poly).each())
        self.assertEqual(len(polys), 1)
        got = polys[0].polygon
        hull = sorted((pt.x, pt.y) for pt in got.each_point_hull())
        self.assertEqual(hull, sorted([(0, 0), (200, 0), (200, 150), (0, 150)]))
        self.assertEqual(got.holes(), 1)
        hole = sorted((pt.x, pt.y) for pt in got.each_point_hole(0))
        self.assertEqual(hole,
                         sorted([(50, 50), (150, 50), (150, 100), (50, 100)]))
        self.assertAlmostEqual(max(x for x, _ in hull) * ly.dbu, 0.2)

        paths = list(top.shapes(li_path).each())
        self.assertEqual(len(paths), 1)
        path = paths[0].path
        self.assertEqual(sorted((pt.x, pt.y) for pt in path.each_point()),
                         sorted([(0, 0), (250, 0)]))
        self.assertEqual(path.width, 10)
        self.assertAlmostEqual(path.width * ly.dbu, 0.01)

        texts = list(top.shapes(li_text).each())
        self.assertEqual(len(texts), 1)
        got_text = texts[0].text
        self.assertEqual(got_text.string, "PAD")
        self.assertEqual((got_text.trans.disp.x, got_text.trans.disp.y),
                         (50, 100))
        self.assertEqual(got_text.size, 20)
        self.assertAlmostEqual(got_text.trans.disp.x * ly.dbu, 0.05)
        self.assertAlmostEqual(got_text.trans.disp.y * ly.dbu, 0.1)

        plain = [i for i in top.each_inst() if not i.is_regular_array()]
        arrays = [i for i in top.each_inst() if i.is_regular_array()]
        self.assertEqual(len(plain), 1)
        self.assertEqual(len(arrays), 1)
        self.assertEqual((plain[0].trans.disp.x, plain[0].trans.disp.y),
                         (500, 1000))
        self.assertAlmostEqual(plain[0].trans.disp.x * ly.dbu, 0.5)
        self.assertAlmostEqual(plain[0].trans.disp.y * ly.dbu, 1.0)
        arr = arrays[0]
        self.assertEqual(arr.cell.name, "CHILD")
        self.assertEqual((arr.cell_inst.a.x, arr.cell_inst.a.y), (1000, 0))
        self.assertEqual((arr.cell_inst.b.x, arr.cell_inst.b.y), (0, 2000))
        self.assertEqual((arr.cell_inst.na, arr.cell_inst.nb), (3, 2))
        self.assertAlmostEqual(arr.cell_inst.a.x * ly.dbu, 1.0)
        self.assertAlmostEqual(arr.cell_inst.b.y * ly.dbu, 2.0)


def add_odd_box(top, li):
    top.shapes(li).insert(kdb.Box(0, 0, 201, 100))


def add_odd_polygon_hull(top, li):
    top.shapes(li).insert(kdb.Polygon(
        [kdb.Point(0, 0), kdb.Point(201, 0), kdb.Point(201, 100),
         kdb.Point(0, 100)]))


def add_odd_polygon_hole(top, li):
    poly = kdb.Polygon([kdb.Point(0, 0), kdb.Point(200, 0),
                        kdb.Point(200, 200), kdb.Point(0, 200)])
    poly.insert_hole([kdb.Point(50, 50), kdb.Point(50, 150),
                      kdb.Point(151, 150), kdb.Point(151, 50)])
    top.shapes(li).insert(poly)


def add_odd_path_point(top, li):
    top.shapes(li).insert(kdb.Path([kdb.Point(0, 0), kdb.Point(201, 0)], 20))


def add_odd_path_width(top, li):
    top.shapes(li).insert(kdb.Path([kdb.Point(0, 0), kdb.Point(200, 0)], 21))


def add_odd_text_origin(top, li):
    text = kdb.Text("T", kdb.Trans(kdb.Vector(101, 20)))
    text.size = 40
    top.shapes(li).insert(text)


def add_odd_text_size(top, li):
    text = kdb.Text("T", kdb.Trans(kdb.Vector(100, 20)))
    text.size = 21
    top.shapes(li).insert(text)


ODD_SHAPE_CASES = [
    ("box_edge", "box", add_odd_box),
    ("polygon_hull", "polygon", add_odd_polygon_hull),
    ("polygon_hole", "polygon", add_odd_polygon_hole),
    ("path_point", "path", add_odd_path_point),
    ("path_width", "path", add_odd_path_width),
    ("text_origin", "text", add_odd_text_origin),
    ("text_size", "text", add_odd_text_size),
]


class OddCoordinateRejection(unittest.TestCase):
    """Each odd field is fatal, is named in the error and modifies nothing."""

    def test_odd_shape_field_raises_and_preserves_the_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, kind, add in ODD_SHAPE_CASES:
                with self.subTest(case=name):
                    ly, top, _child = new_source()
                    li = ly.layer(*GEOM)
                    add(top, li)
                    before = gds_bytes(ly, tmp, f"{name}-before.gds")
                    with self.assertRaises(DbuError) as caught:
                        dbu_export.coarsen(ly)
                    msg = str(caught.exception)
                    self.assertIn("cell 'TOP'", msg)
                    self.assertIn("layer 42/0", msg)
                    self.assertIn(kind, msg)
                    self.assertEqual(ly.dbu, dbu_export.SOURCE_DBU_UM)
                    after = gds_bytes(ly, tmp, f"{name}-after.gds")
                    self.assertEqual(after, before)

    def test_odd_instance_displacement_raises_and_preserves_the_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            ly, top, child = new_source()
            ly.layer(*GEOM)
            top.insert(kdb.CellInstArray(child.cell_index(),
                                         kdb.Trans(kdb.Vector(401, 600))))
            before = gds_bytes(ly, tmp, "disp-before.gds")
            with self.assertRaises(DbuError) as caught:
                dbu_export.coarsen(ly)
            msg = str(caught.exception)
            self.assertIn("cell 'TOP'", msg)
            self.assertIn("instance of CHILD", msg)
            self.assertEqual(ly.dbu, dbu_export.SOURCE_DBU_UM)
            self.assertEqual(gds_bytes(ly, tmp, "disp-after.gds"), before)

    def test_odd_regular_array_pitch_raises_and_preserves_the_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            ly, top, child = new_source()
            ly.layer(*GEOM)
            top.insert(kdb.CellInstArray(child.cell_index(),
                                         kdb.Trans(kdb.Vector(1000, 4000)),
                                         kdb.Vector(2001, 0), kdb.Vector(0, 4000),
                                         2, 2))
            before = gds_bytes(ly, tmp, "pitch-before.gds")
            with self.assertRaises(DbuError) as caught:
                dbu_export.coarsen(ly)
            msg = str(caught.exception)
            self.assertIn("cell 'TOP'", msg)
            self.assertIn("instance of CHILD", msg)
            self.assertEqual(ly.dbu, dbu_export.SOURCE_DBU_UM)
            self.assertEqual(gds_bytes(ly, tmp, "pitch-after.gds"), before)


def marker_layout(child_metal):
    """TOP over CHILD at 0.0005 um: CHILD provides the METAL-layer pin metal,
    TOP carries a 2-DBU property-1 net marker on the same layer."""
    ly, top, child = new_source()
    li = ly.layer(*METAL)
    child.shapes(li).insert(child_metal)
    top.insert(kdb.CellInstArray(child.cell_index(), kdb.Trans(kdb.Vector(0, 0))))
    return ly, top, li


def add_marker(top, li, box, net):
    shape = top.shapes(li).insert(box)
    shape.set_property(dbu_export.DEF_NET_NAME_PROPERTY_ID, net)


class PinMarkerReconstruction(unittest.TestCase):
    """With --pin-markers, property-1 boxes are rebuilt on the target grid."""

    def test_even_marker_halves_exactly_and_keeps_its_net(self):
        ly, top, li = marker_layout(kdb.Box(0, 0, 4, 4))
        add_marker(top, li, kdb.Box(0, 0, 2, 2), "P")

        rebuilt = dbu_export.coarsen(ly, pin_markers=True)

        self.assertEqual(rebuilt, [])
        shapes = list(top.shapes(li).each())
        self.assertEqual(len(shapes), 1)
        self.assertEqual(shapes[0].box, kdb.Box(0, 0, 1, 1))
        self.assertEqual(shapes[0].property(
            dbu_export.DEF_NET_NAME_PROPERTY_ID), "P")

    def test_off_grid_marker_rebuilt_as_smallest_on_grid_box(self):
        ly, top, li = marker_layout(kdb.Box(-4, -2, 2, 4))
        add_marker(top, li, kdb.Box(-3, -2, -1, 0), "P")

        rebuilt = dbu_export.coarsen(ly, pin_markers=True)

        self.assertEqual(
            rebuilt,
            [("TOP", "34/0", "(-3,-2;-1,0)", "(-2,-1;0,0)", "P")])
        shapes = list(top.shapes(li).each())
        self.assertEqual(len(shapes), 1)
        # Each rebuilt axis is floor/ceil of the halved source edge: the
        # smallest on-grid interval containing it (x: -1.5..-0.5 -> -2..0,
        # y halves exactly: -1..0 -> -1..0).
        expected = kdb.Box(math.floor(-3 * 0.5), math.floor(-2 * 0.5),
                           math.ceil(-1 * 0.5), math.ceil(0 * 0.5))
        self.assertEqual(shapes[0].box, expected)
        self.assertEqual(shapes[0].property(
            dbu_export.DEF_NET_NAME_PROPERTY_ID), "P")

    def test_marker_outside_remaining_metal_is_rejected(self):
        # The child metal (0,0;4,4) is elsewhere: the marker (-3,-2;-1,0)
        # rebuilds to (-2,-1;0,0), outside the remaining hierarchical metal.
        ly, top, li = marker_layout(kdb.Box(0, 0, 4, 4))
        add_marker(top, li, kdb.Box(-3, -2, -1, 0), "P")

        with self.assertRaises(DbuError) as caught:
            dbu_export.coarsen(ly, pin_markers=True)

        msg = str(caught.exception)
        self.assertIn("cell 'TOP'", msg)
        self.assertIn("layer 34/0", msg)
        self.assertIn("'P'", msg)

    def test_odd_box_without_property_is_rejected_even_with_marker_handling(self):
        ly, top, li = marker_layout(kdb.Box(-4, -2, 2, 4))
        top.shapes(li).insert(kdb.Box(-3, -2, -1, 0))

        with self.assertRaises(DbuError) as caught:
            dbu_export.coarsen(ly, pin_markers=True)

        msg = str(caught.exception)
        self.assertIn("cell 'TOP'", msg)
        self.assertIn("layer 34/0", msg)
        self.assertIn("box", msg)


class CliMain(unittest.TestCase):
    """main() on temporary streams: --assert-dbu and the no-output guarantee."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name

    def write_stream(self, layout, name):
        path = os.path.join(self.dir, name)
        dbu_export.write_gds(layout, path)
        return path

    @staticmethod
    def target_stream():
        ly = kdb.Layout()
        ly.dbu = dbu_export.TARGET_DBU_UM
        ly.create_cell("OK").shapes(ly.layer(*GEOM)).insert(
            kdb.Box(0, 0, 20, 10))
        return ly

    @staticmethod
    def even_source():
        ly, top, _child = new_source()
        top.shapes(ly.layer(*GEOM)).insert(kdb.Box(0, 0, 200, 100))
        return ly

    @staticmethod
    def odd_source():
        ly, top, _child = new_source()
        top.shapes(ly.layer(*GEOM)).insert(kdb.Box(0, 0, 201, 100))
        return ly

    def test_assert_dbu_accepts_a_target_stream_without_writing(self):
        src = self.write_stream(self.target_stream(), "in.gds")
        self.assertEqual(dbu_export.main(["--assert-dbu", src]), 0)
        self.assertEqual(os.listdir(self.dir), ["in.gds"])

    def test_assert_dbu_rejects_a_source_stream_without_writing(self):
        src = self.write_stream(self.even_source(), "in.gds")
        self.assertEqual(dbu_export.main(["--assert-dbu", src]), 1)
        self.assertEqual(os.listdir(self.dir), ["in.gds"])

    def test_failed_conversion_returns_one_and_writes_no_output(self):
        src = self.write_stream(self.odd_source(), "in.gds")
        out = os.path.join(self.dir, "out.gds")
        self.assertEqual(dbu_export.main([src, out]), 1)
        self.assertFalse(os.path.exists(out))

    def test_successful_conversion_writes_a_target_stream(self):
        src = self.write_stream(self.even_source(), "in.gds")
        out = os.path.join(self.dir, "out.gds")
        self.assertEqual(dbu_export.main([src, out]), 0)
        self.assertTrue(os.path.exists(out))
        back = kdb.Layout()
        back.read(out)
        self.assertEqual(back.dbu, dbu_export.TARGET_DBU_UM)


if __name__ == "__main__":
    unittest.main()
