#!/usr/bin/env python3
"""Regression test: rows place and space leaves on the grown extent (#367, #376).

row_cell and _row_place_all must place on and step on the same (grown) bbox,
so a leaf whose implants grow_mv_pmos_wells / grow_resistor_implants widened
keeps GAP_UM of grown separation from its neighbour even when the two leaves'
overhangs differ (#376: an ungrown leaf followed by a grown one used to lose
the grown leaf's west overhang from the gap). Synthetic in-memory leaves, no
PDK and no klt:

    . signoff/klt.sh && klt_python -I -m unittest discover \
        -s layout -p 'test_row_cell.py' -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_efuse_otp as g  # noqa: E402

import klayout.db as kdb  # noqa: E402

GROW_UM = 1.0
LAYER = (1, 0)


class RowCellGrownExtent(unittest.TestCase):
    def _builder(self, grown):
        """Two-leaf netlist; grown[i] decides whether leaf i carries an anchor
        and a widened implant, as grow_mv_pmos_wells / grow_resistor_implants
        would leave it."""
        b = g.Builder(None, None, {"row": [
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
                reg = kdb.Region(cell.shapes(li)).sized(round(GROW_UM / g.DBU_UM))
                cell.shapes(li).insert(reg)  # grown implant, as grow_mv_pmos_wells
            b.reports[f"{subckt}__{inst['name'][1:]}"] = {
                "bbox_um": {"x0": 0.0, "y0": 0.0}, "ports": []}
            made.append(cell)
            return cell

        b.leaf = leaf
        return b

    def _grown_separation_um(self, row):
        li = row.layout().find_layer(*LAYER)
        grown = []
        for inst in row.each_inst():
            reg = kdb.Region(inst.cell.begin_shapes_rec(li)).transformed(inst.trans)
            grown.append(reg.bbox())
        grown.sort(key=lambda bb: bb.left)
        return (grown[1].left - grown[0].right) * g.DBU_UM

    def _assert_gap(self, row):
        sep_um = self._grown_separation_um(row)
        self.assertGreaterEqual(sep_um, g.GAP_UM - 1e-9,
                                f"grown separation {sep_um:.4f} um < GAP_UM")

    def test_row_cell_both_grown(self):
        b = self._builder((True, True))
        self._assert_gap(b.row_cell("row"))

    def test_row_cell_neither_grown(self):
        b = self._builder((False, False))
        self._assert_gap(b.row_cell("row"))

    def test_row_cell_ungrown_then_grown(self):
        b = self._builder((False, True))
        self._assert_gap(b.row_cell("row"))

    def test_row_cell_grown_then_ungrown(self):
        b = self._builder((True, False))
        self._assert_gap(b.row_cell("row"))

    def test_row_place_all_both_grown(self):
        b = self._builder((True, True))
        cell = b.layout.create_cell("placed")
        b._row_place_all(cell, "row")
        self._assert_gap(cell)

    def test_row_place_all_neither_grown(self):
        b = self._builder((False, False))
        cell = b.layout.create_cell("placed")
        b._row_place_all(cell, "row")
        self._assert_gap(cell)

    def test_row_place_all_ungrown_then_grown(self):
        b = self._builder((False, True))
        cell = b.layout.create_cell("placed")
        b._row_place_all(cell, "row")
        self._assert_gap(cell)

    def test_row_place_all_grown_then_ungrown(self):
        b = self._builder((True, False))
        cell = b.layout.create_cell("placed")
        b._row_place_all(cell, "row")
        self._assert_gap(cell)


if __name__ == "__main__":
    unittest.main()
