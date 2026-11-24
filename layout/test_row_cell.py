#!/usr/bin/env python3
"""Regression test: Builder.row_cell advances on the grown extent (#367).

row_cell and _row_place_all must space leaves on the same (grown) bbox, so a
leaf whose Nwell/Dualgate was widened by grow_mv_pmos_wells keeps GAP_UM of
grown-implant separation from its neighbour. Synthetic in-memory leaves, no
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
    def _builder(self):
        b = g.Builder(None, None, {"row": [
            {"name": "XM1", "kind": "x", "master": "m"},
            {"name": "XM2", "kind": "x", "master": "m"}]})
        b.layout.layer(*LAYER)
        b.leaf = self._leaf(b)
        return b

    @staticmethod
    def _leaf(b):
        made = []

        def leaf(subckt, inst):
            cell = b.layout.create_cell(f"leaf{len(made)}")
            li = b.layout.find_layer(*LAYER)
            cell.shapes(li).insert(kdb.Box(0, 0, 20000, 10000))  # 10 x 5 um
            b.anchor[cell.cell_index()] = cell.bbox()  # footprint, pre-growth
            reg = kdb.Region(cell.shapes(li)).sized(round(GROW_UM / g.DBU_UM))
            cell.shapes(li).insert(reg)  # grown implant, as grow_mv_pmos_wells
            made.append(cell)
            return cell
        return leaf

    def test_grown_separation_at_least_gap(self):
        b = self._builder()
        row = b.row_cell("row")
        li = b.layout.find_layer(*LAYER)
        grown = []
        for inst in row.each_inst():
            reg = kdb.Region(inst.cell.begin_shapes_rec(li)).transformed(inst.trans)
            grown.append(reg.bbox())
        grown.sort(key=lambda bb: bb.left)
        sep_um = (grown[1].left - grown[0].right) * g.DBU_UM
        self.assertGreaterEqual(sep_um, g.GAP_UM - 1e-9)


if __name__ == "__main__":
    unittest.main()
