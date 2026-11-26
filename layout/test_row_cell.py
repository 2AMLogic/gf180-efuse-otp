#!/usr/bin/env python3
"""Regression test: rows place and space leaves on the grown extent (#367, #376, #380).

_row_place_all, coldrv_cell's leaf loop and Builder.size() must place on and
step on the same (grown) bbox, so a leaf whose implants grow_mv_pmos_wells /
grow_resistor_implants widened keeps GAP_UM of grown separation from its
neighbour even when the two leaves' overhangs differ (#376: an ungrown leaf
followed by a grown one used to lose the grown leaf's west overhang from the
gap; #380: coldrv_cell's own cursor carried the same arithmetic with no test,
and Builder.size() still handed out a pre-growth width). Synthetic in-memory
leaves, no PDK and no klt:

    . signoff/klt.sh && klt_python -I -m unittest discover \
        -s layout -p 'test_row_cell.py' -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analog_core import Builder, DBU_UM, GAP_UM  # noqa: E402
from route_drivers import coldrv_cell  # noqa: E402
from route_sense import _row_place_all  # noqa: E402

import klayout.db as kdb  # noqa: E402

GROW_UM = 1.0
LAYER = (1, 0)


def _row_builder(grown):
    """Two-leaf netlist; grown[i] decides whether leaf i carries an anchor
    and a widened implant, as grow_mv_pmos_wells / grow_resistor_implants
    would leave it."""
    b = Builder(None, None, {"row": [
        {"name": "XM1", "kind": "x", "master": "m"},
        {"name": "XM2", "kind": "x", "master": "m"}]})
    b.layout.layer(*LAYER)
    made = []

    def leaf(subckt, inst):
        cell = b.layout.create_cell(f"leaf{len(made)}")
        li = b.layout.find_layer(*LAYER)
        cell.shapes(li).insert(kdb.Box(0, 0, 20000, 10000))  # 10 x 5 um
        if grown[len(made)]:
            b.anchor[cell.cell_index()] = cell.bbox()  # footprint, pre-growth
            reg = kdb.Region(cell.shapes(li)).sized(round(GROW_UM / DBU_UM))
            cell.shapes(li).insert(reg)  # grown implant, as grow_mv_pmos_wells
        b.reports[f"{subckt}__{inst['name'][1:]}"] = {
            "bbox_um": {"x0": 0.0, "y0": 0.0}, "ports": []}
        made.append(cell)
        return cell

    b.leaf = leaf
    return b


class RowPlaceAllGrownExtent(unittest.TestCase):
    def _grown_separation_um(self, row):
        li = row.layout().find_layer(*LAYER)
        grown = []
        for inst in row.each_inst():
            reg = kdb.Region(inst.cell.begin_shapes_rec(li)).transformed(inst.trans)
            grown.append(reg.bbox())
        grown.sort(key=lambda bb: bb.left)
        return (grown[1].left - grown[0].right) * DBU_UM

    def _assert_gap(self, row):
        sep_um = self._grown_separation_um(row)
        self.assertGreaterEqual(sep_um, GAP_UM - 1e-9,
                                f"grown separation {sep_um:.4f} um < GAP_UM")

    def test_row_place_all_both_grown(self):
        b = _row_builder((True, True))
        cell = b.layout.create_cell("placed")
        _row_place_all(b, cell, "row")
        self._assert_gap(cell)

    def test_row_place_all_neither_grown(self):
        b = _row_builder((False, False))
        cell = b.layout.create_cell("placed")
        _row_place_all(b, cell, "row")
        self._assert_gap(cell)

    def test_row_place_all_ungrown_then_grown(self):
        b = _row_builder((False, True))
        cell = b.layout.create_cell("placed")
        _row_place_all(b, cell, "row")
        self._assert_gap(cell)

    def test_row_place_all_grown_then_ungrown(self):
        b = _row_builder((True, False))
        cell = b.layout.create_cell("placed")
        _row_place_all(b, cell, "row")
        self._assert_gap(cell)


class ColdrvGrownExtent(unittest.TestCase):
    """coldrv_cell's own leaf cursor (#380): a third loop with the same
    arithmetic as the row builders' -- one entry per m unit, each advanced
    by the child's grown bbox width plus GAP_UM -- that none of the row
    tests reached. The efuse_ls instance and its attachments are synthetic
    too: coldrv_cell only reads their coordinates, never their geometry
    rules."""

    LS_SHAPE_LAYER = (2, 0)  # the efuse_ls stand-in's bbox shapes; not LAYER,
    # so the grown-separation scan sees leaf units only.

    def _coldrv(self, grown, m=("1", "1")):
        """Two-leaf-device coldrv netlist; grown[i] decides whether device
        i's child carries an anchor and a widened implant, as
        grow_mv_pmos_wells / grow_resistor_implants would leave it. Device i
        is drawn as m[i] placed units (coldrv's Mdrv is m=3 on the real
        netlist), so the within-child adjacency is exercised too."""
        b = Builder(None, None, {"coldrv": [
            {"name": "Xls", "kind": "x", "master": "efuse_ls",
             "nodes": ["in", "out", "vdd33", "vprog", "vss"]},
            {"name": "MM1", "kind": "m", "master": "p",
             "nodes": ["d1", "g1", "vss", "vss"], "params": {"m": m[0]}},
            {"name": "MM2", "kind": "m", "master": "p",
             "nodes": ["d2", "g2", "vss", "vss"], "params": {"m": m[1]}}]})
        b.layout.layer(*LAYER)
        ls = b.layout.create_cell("efuse_ls")
        ls.shapes(b.layout.layer(*self.LS_SHAPE_LAYER)).insert(
            kdb.Box(0, 0, 20000, 20000))  # 10 x 10 um
        b.cells["efuse_ls"] = ls
        b.ls_ports = {i: {p: (x, y, 0.42, 0.0) for p, x, y in ps} for i, ps in {
            "XMni": (("U0_G", 1.0, 1.0),),
            "XMpi": (("U0_G", 1.0, 2.0), ("TAP_W", 0.5, 2.5)),
            "XMn2": (("U0_D", 9.0, 1.0),),
            "XMp2": (("U0_D", 9.0, 2.0), ("TAP_S", 9.5, 0.5)),
            "XMp1": (("TAP_S", 6.0, 0.5),)}.items()}
        made = []

        def leaf(subckt, inst):
            cell = b.layout.create_cell(f"leaf{len(made)}")
            li = b.layout.find_layer(*LAYER)
            cell.shapes(li).insert(kdb.Box(0, 0, 20000, 10000))  # 10 x 5 um
            if grown[len(made)]:
                b.anchor[cell.cell_index()] = cell.bbox()  # footprint, pre-growth
                reg = kdb.Region(cell.shapes(li)).sized(round(GROW_UM / DBU_UM))
                cell.shapes(li).insert(reg)  # grown implant, as grow_mv_pmos_wells
            b.reports[f"{subckt}__{inst['name'][1:]}"] = {"ports": [
                {"name": n, "x_um": x, "y_um": y, "width_um": 0.2}
                for n, x, y in (("U0_S", 1.0, 1.0), ("U0_D", 9.0, 1.0),
                                ("U0_G", 5.0, 4.0), ("TAP_W", 0.5, 2.5),
                                ("TAP_S", 5.0, 0.5))]}
            made.append(cell)
            return cell

        b.leaf = leaf
        return b

    def _grown_row(self, row):
        li = row.layout().find_layer(*LAYER)
        grown = []
        for inst in row.each_inst():
            if not inst.cell.name.startswith("leaf"):
                continue
            reg = kdb.Region(inst.cell.begin_shapes_rec(li)).transformed(inst.trans)
            grown.append(reg.bbox())
        grown.sort(key=lambda bb: bb.left)
        return grown

    def _assert_gap(self, row):
        grown = self._grown_row(row)
        self.assertGreaterEqual(len(grown), 2, "no leaf units placed")
        for west, east in zip(grown, grown[1:]):
            sep_um = (east.left - west.right) * DBU_UM
            self.assertGreaterEqual(sep_um, GAP_UM - 1e-9,
                                    f"grown separation {sep_um:.4f} um < GAP_UM")

    def test_coldrv_both_grown(self):
        b = self._coldrv((True, True))
        self._assert_gap(coldrv_cell(b, "coldrv"))

    def test_coldrv_neither_grown(self):
        b = self._coldrv((False, False))
        self._assert_gap(coldrv_cell(b, "coldrv"))

    def test_coldrv_ungrown_then_grown(self):
        b = self._coldrv((False, True))
        self._assert_gap(coldrv_cell(b, "coldrv"))

    def test_coldrv_grown_then_ungrown(self):
        b = self._coldrv((True, False))
        self._assert_gap(coldrv_cell(b, "coldrv"))

    def test_coldrv_repeated_units(self):
        """Device 1 as its m=3 parallel units (the real Mdrv), each unit of
        the grown leaf followed by an ungrown device 2: the cursor's
        grown-extent arithmetic applies between repeated units too."""
        b = self._coldrv((True, False), m=("3", "1"))
        self._assert_gap(coldrv_cell(b, "coldrv"))


class SizeGuard(unittest.TestCase):
    """Builder.size() hands the top-level floorplan a composite cell's
    extent and refuses a grown leaf outright (#380): place() anchors x on
    the grown bbox, so a pre-growth width stepped into a cursor would
    re-create #376."""

    def test_size_rejects_grown_leaf(self):
        b = _row_builder((True, False))
        cell = b.layout.create_cell("placed")
        _row_place_all(b, cell, "row")
        grown = b.layout.cell("leaf0")
        self.assertIn(grown.cell_index(), b.anchor)
        with self.assertRaises(AssertionError):
            b.size(grown)

    def test_size_takes_composite_extent(self):
        b = _row_builder((True, True))
        cell = b.layout.create_cell("placed")
        _row_place_all(b, cell, "row")
        w, h = b.size(cell)
        self.assertGreaterEqual(w, 2 * (10.0 + 2 * GROW_UM) + GAP_UM - 1e-9)
        self.assertGreaterEqual(h, 5.0 + 2 * GROW_UM - 1e-9)
