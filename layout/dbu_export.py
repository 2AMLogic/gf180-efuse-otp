#!/usr/bin/env python3
"""Emit a GDS stream at the foundry database unit (issue #311).

gf180mcu's full `geom.rb` deck requires the design database unit to be
0.001 um (its `DBU` rule, one marker on each partition in #313's native
reports). Both partition producers build on klt's 0.0005 um working grid:
`klt gen` writes 0.0005 um for gf180mcu (2AMLogic/klayout-tools#5721) and
so does the pinned 0.9.2 place-and-route merge. klt 0.9.2's
`output_dbu_um` accepts whole-number refinement only
(2AMLogic/klayout-tools#4482), so the 2:1 coarsening is done here, at the
final write:

* Every integer the stream stores -- shape vertices (hull and holes), box
  and path points, path widths, text origins and sizes, instance
  displacements and array pitches -- must be even. An odd one is fatal and
  is reported with its cell and layer; nothing is written.
* The layout is scaled by 1/2 and its dbu set to TARGET_DBU_UM: every even
  coordinate halves exactly, so the micron geometry, hierarchy, labels and
  properties are unchanged.
* The one sanctioned exception is the P&R single-pin net markers: 2-DBU
  boxes carrying their DEF net name in GDS property 1, centred on the pin
  (`place_and_route_gds_merge._SINGLE_PIN_NET_MARKER_HALF_DBU = 1`). A
  marker axis whose source centre is odd halves exactly; the other axes
  become the smallest on-grid box containing the original one (at most half
  a target DBU wider per side). Each reconstruction is checked to lie
  inside the remaining hierarchical metal of its own layer, so every net
  name stays on its connected pin metal.

Usage (controller stream, markers reconstructed):

    klt_python -I layout/dbu_export.py --pin-markers IN.gds OUT.gds

`--assert-dbu IN.gds` only reads the stream's declared unit and exits
non-zero unless it is the target one. The array generator imports this
module instead (see gen_efuse_otp.py's build): it allows no odd
coordinate at all.
"""

import argparse
import sys

import klayout.db as kdb

TARGET_DBU_UM = 0.001  # gf180mcu geom.rb `DBU`: the design dbu must be 0.001
SOURCE_DBU_UM = 0.0005  # klt's working grid for gf180mcu (klt gen, P&R merge)
# klt's extract pins this property id for DEF net names on layout shapes.
DEF_NET_NAME_PROPERTY_ID = 1


class DbuError(Exception):
    """An unrepresentable coordinate: the stream cannot be coarsened."""


def _shape_coords(shape):
    """(kind, ints): every integer the 2:1 conversion must divide evenly."""
    if shape.is_box():
        b = shape.box
        return "box", (b.left, b.bottom, b.right, b.top)
    if shape.is_polygon():
        p = shape.polygon
        pts = [c for pt in p.each_point_hull() for c in (pt.x, pt.y)]
        for hole in range(p.holes()):
            pts += [c for pt in p.each_point_hole(hole) for c in (pt.x, pt.y)]
        return "polygon", pts
    if shape.is_path():
        p = shape.path
        pts = [c for pt in p.each_point() for c in (pt.x, pt.y)] + [p.width]
        return "path", pts
    if shape.is_text():
        t = shape.text
        return "text", (t.trans.disp.x, t.trans.disp.y, t.size)
    return "other", ()


def _inst_coords(inst):
    cs = [inst.trans.disp.x, inst.trans.disp.y]
    if inst.is_regular_array():
        a, b = inst.cell_inst.a, inst.cell_inst.b
        cs += [a.x, a.y, b.x, b.y]
    return cs


def _is_pin_marker(shape):
    """A 2-DBU box carrying a DEF net name in GDS property 1 (klt's marker)."""
    if not shape.is_box():
        return False
    name = shape.property(DEF_NET_NAME_PROPERTY_ID)
    return isinstance(name, str) and bool(name)


def coarsen(layout, pin_markers=False):
    """Scale `layout` from SOURCE_DBU_UM to TARGET_DBU_UM in place.

    Exact for every even coordinate; the odd ones must be single-pin net
    markers (and only when `pin_markers`), which are re-drawn on the target
    grid inside the remaining metal of their own layer. Returns the list of
    rebuilt markers as (cell, layer, source box, rebuilt box, net name).
    Raises DbuError (nothing modified) on any other odd coordinate.
    """
    if abs(layout.dbu - SOURCE_DBU_UM) > 1e-12:
        raise DbuError(f"expected a {SOURCE_DBU_UM} um stream, found {layout.dbu} um")

    markers = {}  # (cell_index, layer_index) -> (cell, layer, [(box, net name)])
    for cell in layout.each_cell():
        for inst in cell.each_inst():
            cs = _inst_coords(inst)
            if any(c % 2 for c in cs):
                raise DbuError(
                    f"cell '{cell.name}': instance of {inst.cell.name} has odd "
                    f"coordinate(s) {cs}; {TARGET_DBU_UM} um cannot represent "
                    f"them exactly")
        for li in layout.layer_indexes():
            info = layout.get_info(li)
            layer = f"{info.layer}/{info.datatype}"
            shapes = cell.shapes(li)
            doomed = []
            for shape in shapes.each():
                kind, coords = _shape_coords(shape)
                if not any(c % 2 for c in coords):
                    continue
                if not (pin_markers and _is_pin_marker(shape)):
                    raise DbuError(
                        f"cell '{cell.name}' layer {layer}: {kind} coordinate(s) "
                        f"{coords} are odd; {TARGET_DBU_UM} um cannot represent "
                        f"them exactly")
                doomed.append((shape, shape.property(DEF_NET_NAME_PROPERTY_ID)))
            if doomed:
                entry = markers.setdefault(
                    (cell.cell_index(), li), (cell, layer, []))
                for shape, name in doomed:
                    entry[2].append((shape.box, name))
                    shape.delete()  # the scale must not touch the odd boxes

    layout.transform(kdb.ICplxTrans(SOURCE_DBU_UM / TARGET_DBU_UM))
    layout.dbu = TARGET_DBU_UM

    rebuilt = []
    for (ci, li), (cell, layer, items) in markers.items():
        # The coverage region is the remaining hierarchical metal of this
        # layer: the markers were removed above, so it is the pin metal.
        metal = kdb.Region(cell.begin_shapes_rec(li))
        for box, name in items:
            # Smallest on-grid box containing the halved source box: an axis
            # with an odd source centre halves exactly, the others grow by at
            # most half a target DBU per side.
            nb = kdb.Box(box.left // 2, box.bottom // 2,
                         -(-box.right // 2), -(-box.top // 2))
            outside = kdb.Region()
            outside.insert(nb)
            if (outside - metal).count():
                raise DbuError(
                    f"cell '{cell.name}' layer {layer}: reconstructed marker "
                    f"{nb.to_s()} for net {name!r} is not inside the remaining "
                    f"metal; the pin the source box {box.to_s()} sat on does "
                    f"not cover it")
            shape = cell.shapes(li).insert(nb)
            shape.set_property(DEF_NET_NAME_PROPERTY_ID, name)
            rebuilt.append((cell.name, layer, box.to_s(), nb.to_s(), name))
    return rebuilt


def write_gds(layout, out_path):
    opts = kdb.SaveLayoutOptions()
    opts.format = "GDS2"
    opts.gds2_write_timestamps = False
    layout.write(str(out_path), opts)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("input", help="source stream (dbu 0.0005 um)")
    ap.add_argument("output", nargs="?", help="coarsened stream (dbu 0.001 um)")
    ap.add_argument("--pin-markers", action="store_true",
                    help="reconstruct odd single-pin net markers (property 1) "
                         "on the target grid inside their pin metal")
    ap.add_argument("--assert-dbu", action="store_true",
                    help="only check the input's declared dbu (no output written)")
    a = ap.parse_args(argv)
    layout = kdb.Layout()
    layout.read(a.input)
    if a.assert_dbu:
        if abs(layout.dbu - TARGET_DBU_UM) > 1e-12:
            print(f"{a.input}: dbu {layout.dbu} um, expected {TARGET_DBU_UM} um",
                  file=sys.stderr)
            return 1
        return 0
    if not a.output:
        ap.error("an output path is required unless --assert-dbu is given")
    try:
        coarsen(layout, pin_markers=a.pin_markers)
    except DbuError as e:
        print(f"dbu_export: {a.input}: {e}", file=sys.stderr)
        return 1
    write_gds(layout, a.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
