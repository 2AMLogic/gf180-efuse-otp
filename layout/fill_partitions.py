#!/usr/bin/env python3
"""Insert density fill into a partition stream (#310).

Run with the pinned klt's interpreter (``klt_python``, see signoff/klt.sh):
only ``klayout.db`` is used, and the output stream is written with GDS
timestamps off. The analog regeneration script orders the emitted boundary
elements before computing the array stream digest.

What it adds, inside the design extent (the top cell's bounding box) only:

* **COMP dummy** (22/4) and **Poly2 dummy** (30/4) in one FEOL pattern:
  a lattice of 6 um squares at 8 um pitch plus one frame strip along each
  die edge, sized to the free band; each lattice square then carries a
  Poly2 dummy square 0.3 um larger on every side (6.6 um) on the same site
  where the dummy-poly2 keep-outs allow it, so every merged poly2 dummy
  polygon strictly covers its comp dummy polygon -- the relation the deck's
  DPF.1 check (`poly2_dummy.not_covering(comp_dummy)`) demands, and the
  same 5.0/5.6 relation the PDK's own fill scripts use.
* **Metal1..Metal5 dummy** (34/4, 36/4, 42/4, 46/4, 81/4) per layer: the
  same frame + a lattice of 6 um squares at 7 um pitch, then a second pass
  of 3 um squares at 4 um pitch over what remains. Metal2 alone then gets a
  third pass of 2 um squares at 3 um pitch over what still remains (#365):
  the bitcell/row routing's 2 um space to drawn metal leaves bands too narrow
  for a 3 um square, and the two passes left M2.4 short. On the 5-level stack
  Metal5 is MetalTop, so the Metal5 fill serves M5.4 and MT.3 together.

Every keep-out below is a foundry rule value from the PDK's own DRC rule
decks at open_pdks ``f6eeac7`` (``libs.tech/klayout/tech/drc/rule_decks/``),
checked by the same native deck ``layout/drc.sh`` replays; the one number
that is not a rule is the 6 um space kept from every fuse marker on every
filled layer, which adopts DM.8's dummy-metal-to-fuse-marker space as the
fuse keep-out for all fill (this PDK's eFuse marks itself with PLFUSE
125/5 and EFUSE_MK 80/5, which DM.8 does not list). No deck rule bounds a
dummy square's width (see ``METAL_THIRD_SIZE``). All geometry is on the
0.005 um rule grid: sizes, pitches, halos and keeps are multiples of it
and the metal dummy-dummy keep uses 1.0 um where DM.2b asks 0.98.

Feed layers are read flattened from the top cell, merged; the fill shapes
land in one new cell ``density_fill`` instantiated once at the top, so no
sub-cell (no routed cell, no via2-bearing cell) changes.
"""

import argparse
import json
import sys
from pathlib import Path

import klayout.db as kdb

# --- layers (gf180mcu, drawing datatype 0, dummy datatype 4) -----------------
COMP, COMP_DUMMY = (22, 0), (22, 4)
POLY2, POLY2_DUMMY = (30, 0), (30, 4)
METALS = {1: (34, 0), 2: (36, 0), 3: (42, 0), 4: (46, 0), 5: (81, 0)}
METAL_DUMMY = {n: (ld[0], 4) for n, ld in METALS.items()}
NWELL, DNWELL, LVPWELL, DUALGATE = (21, 0), (12, 0), (204, 0), (55, 0)
RES_MK, NDMY, PMNDMY = (110, 5), (111, 5), (152, 5)
PAD, IND_MK, MTPMK = (37, 0), (151, 5), (122, 5)
# Fuse markers: ours (PLFUSE, EFUSE_MK) plus every marker DM.8 names.
FUSE_MARKS = [(125, 5), (80, 5), (75, 0), (220, 0), (96, 1), (152, 5), (122, 5), (173, 5)]

FUSE_KEEPOUT_UM = 6.0  # DM.8's dummy-to-fuse-marker space, applied to all fill

# --- FEOL keep-outs (COMP dummy): DCF.2b/4/5/6abcd/8a/11a/12 ------------------
COMP_HALOS = [
    (COMP, 3.5),      # DCF.4 space to circuit COMP
    (POLY2, 1.5),     # DCF.5 space to poly2
    (NWELL, 1.3),     # DCF.6a
    (DNWELL, 4.0),    # DCF.6b
    (LVPWELL, 1.3),   # DCF.6c
    (DUALGATE, 1.3),  # DCF.6d
    (RES_MK, 3.5),    # DCF.8a
    (NDMY, 3.5),      # DCF.11a
    (IND_MK, 3.0),    # DCF.12
    (PAD, 6.7),       # fill_comp.rb's DCF.9 pad space, kept conservatively
]
# --- Poly2 dummy keep-outs: DPF.4/5/6abcd/8/9/11/14/16/19 --------------------
POLY2_HALOS = [
    (COMP, 3.2),      # DPF.4
    (POLY2, 5.0),     # DPF.5
    (NWELL, 1.0),     # DPF.6a
    (DNWELL, 2.0),    # DPF.6b
    (LVPWELL, 1.0),   # DPF.6c
    (DUALGATE, 1.0),  # DPF.6d
    (RES_MK, 19.7),   # DPF.8
    (PAD, 6.7),       # DPF.9
    (NDMY, 29.7),     # DPF.11
    (IND_MK, 3.0),    # DPF.14
    (MTPMK, 3.0),     # DPF.16
    (PMNDMY, 8.0),    # DPF.19
]
METAL_SPACE_UM = 2.0  # DM.n.3 space to same-layer circuit metal

# --- fill pattern ------------------------------------------------------------
FEOL_SIZE, FEOL_GAP = 6.0, 2.0   # gap >= DCF.2b 1.9
FEOL_COVER_OVERHANG_UM = 0.3  # poly2 cover square overhangs its comp square
                              # per side, so it strictly covers it (DPF.1);
                              # the PDK's own fill uses 5.0 um comp under
                              # 5.6 um poly2
POLY2_ANNULUS_MARGIN_UM = 0.3  # comp annulus = poly2 annulus eroded by this
POLY2_GAP_MIN_UM = 1.1  # DPF.2b: keep covers this far from the poly2 annulus
METAL_SIZE, METAL_GAP = 6.0, 1.0  # gap >= DM.n.2b 0.98 (1.0 stays on grid)
METAL2_SIZE, METAL2_GAP = 3.0, 1.0
# Third pass, Metal2 only (#365). The pinned deck sets no dummy-metal width:
# rule_decks/dummy_metal.rb checks DM.n.2b (space), DM.n.3 and DM.n.8 only,
# and M2.1 runs on metal2_drawn 36/0, not metal2_dummy 36/4 (metal.rb,
# generic_layers.rb). The size therefore follows the PDK's own fill,
# scripts/fill_metal.rb, which draws a 2.0 um square under its "DM.1" comment.
METAL_THIRD_SIZE, METAL_THIRD_GAP = 2.0, 1.0
METAL_THIRD_LAYERS = (2,)  # layer numbers that get the third pass
FRAME_MAX_W_UM = 25.0
FRAME_STEP_UM = 0.5
GRID_UM = 0.005  # the rule grid; every size above is a multiple of it


def region(ly, top, ld):
    idx = ly.find_layer(*ld)
    r = kdb.Region()
    if idx is not None:
        r = kdb.Region(ly.begin_shapes(top, idx))
        r.merge()
    return r


def halos(ly, top, dbu, table, fuse):
    """Union of each feed layer sized out by its rule value, plus the fuse keep-out."""
    out = kdb.Region()
    for ld, um in table:
        out += region(ly, top, ld).sized(round(um / dbu))
    return out + fuse.sized(round(FUSE_KEEPOUT_UM / dbu))


def frame(ext, halos_r, dbu, keep_um):
    """One strip along each die edge: the widest (FRAME_STEP grid) full-length
    edge band that lies in free area, clipped by the strips already placed
    (each earlier strip keeps `keep_um` to the next piece)."""
    E = ext.bbox()
    fill = kdb.Region()
    blocker = halos_r.dup()
    keep = round(keep_um / dbu)
    w = FRAME_STEP_UM
    best = {s: None for s in "NSWE"}
    while w <= FRAME_MAX_W_UM:
        wd = round(w / dbu)
        boxes = {
            "N": kdb.Box(E.left, E.top - wd, E.right, E.top),
            "S": kdb.Box(E.left, E.bottom, E.right, E.bottom + wd),
            "W": kdb.Box(E.left, E.bottom, E.left + wd, E.top),
            "E": kdb.Box(E.right - wd, E.bottom, E.right, E.top),
        }
        for side, box in boxes.items():
            rb = kdb.Region(box)
            if (rb - halos_r).area() == rb.area():
                best[side] = rb
        w += FRAME_STEP_UM
    for side in "NSWE":
        if best[side] is None:
            continue
        piece = best[side] - blocker
        if piece.is_empty():
            continue
        fill += piece
        blocker += piece.sized(keep)
    return fill


def lattice_boxes(ext, blocker, dbu, size_um, gap_um):
    """`size_um` squares at `size+gap` pitch, anchored on the rule grid at the
    free area's lower-left; only squares entirely inside free area are kept."""
    E = ext.bbox()
    free = ext - blocker
    bb = free.bbox()
    out = []
    if bb.empty():
        return out
    g = round(GRID_UM / dbu)
    sd = round(size_um / dbu)
    pd = round((size_um + gap_um) / dbu)
    x0 = (bb.left + g - 1) // g * g
    y0 = (bb.bottom + g - 1) // g * g
    y = y0
    while y + sd <= bb.top:
        x = x0
        while x + sd <= bb.right:
            out.append(kdb.Box(x, y, x + sd, y + sd))
            x += pd
        y += pd
    if not out:
        return out
    # batched inside test (one region op, not one per square)
    sq = kdb.Region()
    for box in out:
        sq.insert(box)
    kept = []
    for p in sq.inside(free).each():
        kept.append(p.bbox())
    kept.sort(key=lambda b: (b.bottom, b.left))
    return kept


def fill_class(ext, halos_r, dbu, keep_um, sizes):
    """Frame plus lattice passes, each pass kept `keep_um` from the last."""
    keep = round(keep_um / dbu)
    fill = frame(ext, halos_r, dbu, keep_um)
    blocker = halos_r.dup() + fill.sized(keep)
    for size, gap in sizes:
        sq = kdb.Region()
        for box in lattice_boxes(ext, blocker, dbu, size, gap):
            sq.insert(box)
        fill += sq
        blocker += sq.sized(keep)
    return fill


def metal_passes(n):
    """(square, gap) lattice passes for metal layer n: the 6 um and 3 um
    squares every layer gets, then for Metal2 alone the 2 um third pass."""
    passes = [(METAL_SIZE, METAL_GAP), (METAL2_SIZE, METAL2_GAP)]
    if n in METAL_THIRD_LAYERS:
        passes.append((METAL_THIRD_SIZE, METAL_THIRD_GAP))
    return passes


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--top", default=None)
    a = ap.parse_args()

    ly = kdb.Layout()
    ly.read(a.input)
    tops = [c for c in ly.top_cells()]
    top = ly.cell(a.top) if a.top else (tops[0] if len(tops) == 1 else None)
    if top is None:
        return "stream has several top cells; pass --top"
    dbu = ly.dbu
    ext = kdb.Region(top.bbox())
    extent_area = ext.area()  # square database units

    fuse = kdb.Region()
    for ld in FUSE_MARKS:
        fuse += region(ly, top, ld)
    fuse.merge()

    fill_cell = ly.create_cell("density_fill")

    report = {
        "schema_version": 1,
        "input": Path(a.input).name,
        "output": Path(a.output).name,
        "top_cell": top.name,
        "dbu_um": dbu,
        "extent_um": [round(v * dbu, 4) for v in
                      (top.bbox().left, top.bbox().bottom, top.bbox().right, top.bbox().top)],
        "extent_area_um2": round(extent_area * dbu * dbu, 1),
        "fill_cell": "density_fill",
        "fuse_keepout_um": FUSE_KEEPOUT_UM,
        "keepouts": {
            "comp_dummy": {f"{ld[0]}/{ld[1]}": um for ld, um in COMP_HALOS},
            "poly2_dummy": {f"{ld[0]}/{ld[1]}": um for ld, um in POLY2_HALOS},
            "metal_dummy_same_layer": METAL_SPACE_UM,
            "fuse_markers_um": FUSE_KEEPOUT_UM,
        },
        "pattern_um": {
            "feol_square": FEOL_SIZE, "feol_pitch": FEOL_SIZE + FEOL_GAP,
            "metal_square": METAL_SIZE, "metal_pitch": METAL_SIZE + METAL_GAP,
            "metal_second_square": METAL2_SIZE, "metal_second_pitch": METAL2_SIZE + METAL2_GAP,
            "metal_third_square": METAL_THIRD_SIZE,
            "metal_third_pitch": METAL_THIRD_SIZE + METAL_THIRD_GAP,
            "metal_third_layers": [f"Metal{n}" for n in METAL_THIRD_LAYERS],
            "frame_max_width": FRAME_MAX_W_UM,
        },
        "layers": [],
    }

    def emit(name, drawing_ld, dummy_ld, fill, drawn, rule, bound, desc, upper_limit=None):
        li = fill_cell.shapes(ly.layer(*dummy_ld))
        n = 0
        for p in fill.each():
            li.insert(p)
            n += 1
        # Cross-multiply in square database units, including equality at each bound.
        covered = 100 * (drawn + fill).area()
        passes = covered >= bound * extent_area
        if upper_limit is not None:
            upper_rule, maximum = upper_limit
            if covered > maximum * extent_area:
                rule, bound = upper_rule, maximum
                passes = False
        row = {
            "name": name, "drawing": f"{drawing_ld[0]}/{drawing_ld[1]}",
            "fill_layer": f"{dummy_ld[0]}/{dummy_ld[1]}",
            "drawn_pct": 100 * drawn.area() / extent_area,
            "fill_pct": 100 * fill.area() / extent_area, "total_pct": covered / extent_area,
            "fill_shapes": n, "rule": rule, "bound": bound, "description": desc,
            "pass": passes,
        }
        report["layers"].append(row)

    comp = region(ly, top, COMP)
    poly2 = region(ly, top, POLY2)
    # FEOL. One poly2 annulus at the die edge (per side, the widest strip
    # that fits the dummy-poly2 keep-outs; the four sides merge at the
    # corners), with its comp annulus underneath: comp_ann = poly2_ann
    # eroded POLY2_ANNULUS_MARGIN, so the merged poly2 polygon strictly
    # covers the merged comp polygon -- the relation the deck's DPF.1 check
    # (`poly2_dummy.not_covering(comp_dummy)`) demands, the same 5.0/5.6
    # relation the PDK's own fill scripts use. Then a comp lattice of 6 um
    # squares at 8 um pitch over the remaining comp free area, each square
    # optionally carrying a 6.6 um poly2 square concentrically (0.3 um
    # larger on every side, so it strictly covers the comp square) where
    # the dummy-poly2 keep-outs allow. Comp squares keep DCF.2b's 1.9 um
    # from the comp annulus; poly2 squares keep DPF.2b's 1.1 um from the
    # poly2 annulus (the comp keep plus the erosion margin already give
    # >= 1.3 um; the explicit subtraction is belt and braces).
    comp_h = halos(ly, top, dbu, COMP_HALOS, fuse)
    poly2_h = halos(ly, top, dbu, POLY2_HALOS, fuse)
    poly2_free = ext - poly2_h
    E = ext.bbox()
    poly2_ann = kdb.Region()
    best = {s: None for s in "NSWE"}
    w = FRAME_STEP_UM
    while w <= FRAME_MAX_W_UM:
        wd = round(w / dbu)
        boxes = {
            "N": kdb.Box(E.left, E.top - wd, E.right, E.top),
            "S": kdb.Box(E.left, E.bottom, E.right, E.bottom + wd),
            "W": kdb.Box(E.left, E.bottom, E.left + wd, E.top),
            "E": kdb.Box(E.right - wd, E.bottom, E.right, E.top),
        }
        for side, box in boxes.items():
            rb = kdb.Region(box)
            if (rb - poly2_free).area() == 0:
                best[side] = rb
        w += FRAME_STEP_UM
    for side in "NSWE":
        if best[side] is not None:
            poly2_ann += best[side]
    poly2_ann.merge()
    comp_ann = poly2_ann.sized(-round(POLY2_ANNULUS_MARGIN_UM / dbu)) \
        & (ext - comp_h)
    comp_blocker = comp_h + comp_ann.sized(round(FEOL_GAP / dbu))
    comp_sites = lattice_boxes(ext, comp_blocker, dbu, FEOL_SIZE, FEOL_GAP)
    over = round(FEOL_COVER_OVERHANG_UM / dbu)
    covers_free = poly2_free - poly2_ann.sized(round(POLY2_GAP_MIN_UM / dbu))
    comp_fill = comp_ann.dup()
    poly2_fill = poly2_ann.dup()
    cands = kdb.Region()
    for box in comp_sites:
        cands.insert(kdb.Box(box.left - over, box.bottom - over,
                             box.right + over, box.top + over))
    for p in cands.inside(covers_free).each():
        b = p.bbox()
        comp_fill.insert(kdb.Box(b.left + over, b.bottom + over,
                                 b.right - over, b.top - over))
        poly2_fill.insert(b)
    emit("COMP", COMP, COMP_DUMMY, comp_fill, comp, "DCF.1b", 25,
         "COMP+dummy over extent, DCF.1b >= 25% / DCF.1d <= 70%", upper_limit=("DCF.1d", 70))
    emit("Poly2", POLY2, POLY2_DUMMY, poly2_fill, poly2, "PL.8", 14,
         "Poly2+dummy over extent, PL.8 >= 14% (dummy poly2 covers dummy COMP, DPF.1)")

    for n, ld in METALS.items():
        drawn = region(ly, top, ld)
        metal_h = halos(ly, top, dbu, [(ld, METAL_SPACE_UM)], fuse)
        mfill = fill_class(ext, metal_h, dbu, METAL_GAP, metal_passes(n))
        emit(f"Metal{n}", ld, METAL_DUMMY[n], mfill, drawn, f"M{n}.4", 30,
             f"Metal{n}+dummy over extent, M{n}.4 >= 30%"
             + ("; MT.3 >= 30% shares this layer on the 5-level stack" if n == 5 else ""))

    report["all_pass"] = all(row["pass"] for row in report["layers"])
    for row in report["layers"]:
        print(f"{row['name']}: {row['drawn_pct']:.8g}% drawn + {row['fill_pct']:.8g}% fill "
              f"= {row['total_pct']:.8g}% [{row['rule']}, {'pass' if row['pass'] else 'FAIL'}]",
              file=sys.stdout if report["all_pass"] else sys.stderr)
    if not report["all_pass"]:
        return 5

    top.insert(kdb.CellInstArray(fill_cell.cell_index(), kdb.Trans()))
    opts = kdb.SaveLayoutOptions()
    opts.format = "GDS2"
    opts.gds2_write_timestamps = False
    ly.write(a.output, opts)
    Path(a.report).write_text(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
