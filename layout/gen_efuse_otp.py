#!/usr/bin/env python3
"""Generate layout/efuse_otp_array.gds (analog partition) from the netlist.

Run it through layout/regen-gds.sh, which supplies the pinned klt and PDK:
the interpreter must be the pinned klt's own (it provides klayout.db) and the
leaf devices are produced by that same klt (`klt gen`).

The generator is split by routing responsibility: analog_core.py holds the
SPICE parser, the grid/layer constants and the placement Builder with the
shared drawing primitives; route_ls.py, route_drivers.py, route_sense.py and
route_array.py each draw one cell family; this module keeps the CLI, build,
hierarchy assembly, fuse verification, export and reporting.

What it does
  * Reads design/efuse_otp_array.spice (the netlist derived from the committed
    schematics) and builds one cell per subcircuit, named as the subcircuit, so
    the layout hierarchy is the schematic hierarchy.
  * Every MOS device becomes a `klt gen mos_array` cell at the netlist W and L
    (folded into fingers of at most MAX_FINGER_W_UM, same total W). Every
    `efuse` device becomes the PDK primitive, copied unmodified.
  * Sub-cells are placed in a row per subcircuit; the 32 x 8 array, the row
    drivers and the column drivers are hierarchical array instances.
  * `efuse_ls` is placed on a stated two-row floorplan and routed with
    generator-drawn geometry (M2 horizontal, M3 vertical, via1/via2 stacks), so
    the cell is a circuit (see ls_cell and layout/README.md, "efuse_ls
    routing"). `efuse_rowdrv` (one efuse_ls) and `efuse_coldrv` (12 devices,
    Mdrv drawn as its m=3 parallel units, and one efuse_ls) are routed the
    same way (rowdrv_cell, coldrv_cell). `efuse_comp` (seven MOS, one row)
    and `efuse_sense` (twenty leaves and the routed efuse_comp instance) are
    routed the same way (comp_cell, sense_cell): one via1 + M2 pad + via2 +
    M3 lane per signal pin, one M2 track per multi-pin net above the row,
    supply rails below it, and the PDK resistors drawn at the netlist's stated
    geometry. `efuse_bitcell` (the PDK fuse plus the 180-deg-rotated select
    NFET), `efuse_row` (8 bitcells plus the shared wl/vss rails) and the array
    top `efuse_otp_array` (32 rows, 32 row drivers, 8 column drivers and the
    sense block, wired on M2/M3/M4/M5) are routed too (bitcell_cell,
    array_row_cell, route_array_top; see layout/README.md).

What it does not do: verify DRC, EF.* coverage or LVS itself (those are
separate scripts; see layout/README.md).
"""

import argparse
import hashlib
import json
import shlex
import sys
import tempfile
from pathlib import Path

import klayout.db as kdb

# klt_python -I (isolated mode) does not add this script's directory to
# sys.path; the core builder and the per-cell routers live beside it.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dbu_export
from analog_core import (DBU_UM, GAP_UM, RSH_PPOLYF_U, Builder, Klt, masters,
                         parse_netlist, snap)
from route_array import COLS, ROWS, array_row_cell, bitcell_cell, route_array_top
from route_drivers import coldrv_cell, rowdrv_cell
from route_ls import ls_cell
from route_sense import comp_cell, sense_cell


def verify_fuse(layout, cell_name, pdk_gds):
    """Exit 4 unless the placed fuse cell is geometry-equal to the PDK stream.

    Compares flattened shapes per layer against the PDK file read fresh; the
    two streams differ in dbu and cell name, so the PDK side is scaled by the
    exact integer dbu ratio.
    """
    ref = kdb.Layout()
    ref.read(pdk_gds)
    ref_top = ref.top_cell()
    cell = layout.cell(cell_name)
    scale = ref.dbu / layout.dbu
    ref_layers = set()
    for li in ref.layer_indexes():
        info = ref.get_info(li)
        if not kdb.Region(ref_top.begin_shapes_rec(li)).count():
            continue  # text-only layer (the PDK cell's in/out port labels)
        ref_layers.add((info.layer, info.datatype))
        mi = layout.find_layer(info.layer, info.datatype)
        mine = kdb.Region(cell.begin_shapes_rec(mi)) if mi is not None else kdb.Region()
        theirs = kdb.Region(ref_top.begin_shapes_rec(li)).transformed(kdb.ICplxTrans(scale))
        if (mine ^ theirs).count():
            print(f"fuse differs from the PDK primitive on layer {info.layer}/{info.datatype}",
                  file=sys.stderr)
            sys.exit(4)
    mine_layers = {(layout.get_info(i).layer, layout.get_info(i).datatype)
                   for i in layout.layer_indexes()
                   if kdb.Region(cell.begin_shapes_rec(i)).count()}
    if mine_layers != ref_layers:
        print("fuse geometry layer set differs from the PDK primitive", file=sys.stderr)
        sys.exit(4)


def build(netlist_path, klt, fuse_gds, out_gds, report_json):
    netlist = parse_netlist(netlist_path)
    top = "efuse_otp_array"
    assert masters(netlist, top) == {
        "efuse_rowdrv": ROWS, "efuse_coldrv": COLS, "efuse_row": ROWS, "efuse_sense": 1}, \
        "netlist top no longer matches the floorplan"
    assert masters(netlist, "efuse_row") == {"efuse_bitcell": COLS}, "efuse_row is not 8 bitcells"

    b = Builder(klt, fuse_gds, netlist)
    # Leaf-level subcircuits first, in dependency order. efuse_bitcell and
    # efuse_ls are routed (route_array.bitcell_cell, route_ls.ls_cell),
    # efuse_rowdrv / efuse_coldrv are routed from it and leaf devices
    # (route_drivers.rowdrv_cell, coldrv_cell), efuse_comp and efuse_sense
    # the same way (route_sense.comp_cell, sense_cell).
    bitcell_cell(b, "efuse_bitcell")
    ls_cell(b, "efuse_ls")
    rowdrv_cell(b, "efuse_rowdrv")
    coldrv_cell(b, "efuse_coldrv")
    comp_cell(b, "efuse_comp")
    sense_cell(b, "efuse_sense")

    bit_w, _ = b.size(b.cells["efuse_bitcell"])
    rd_w, rd_h = b.size(b.cells["efuse_rowdrv"])
    cd_w, cd_h = b.size(b.cells["efuse_coldrv"])
    sa_w, sa_h = b.size(b.cells["efuse_sense"])
    pitch_x = max(bit_w, cd_w) + GAP_UM  # bit lines line up with the column drivers
    row = array_row_cell(b, pitch_x)  # 8 routed bitcells at the column pitch
    _, row_h = b.size(row)
    pitch_y = max(row_h, rd_h) + GAP_UM  # word lines line up with the row drivers

    t = b.layout.create_cell(top)
    row_xy = b.place(t, row, 0.0, 0.0, ROWS, 1, 0.0, pitch_y)
    rd_xy = b.place(t, b.cells["efuse_rowdrv"], -(rd_w + GAP_UM), 0.0, ROWS, 1, 0.0, pitch_y,
                    away_x=False)
    cd_xy = b.place(t, b.cells["efuse_coldrv"], 0.0, -(cd_h + GAP_UM), 1, COLS, pitch_x,
                    away_y=False)
    sa_xy = b.place(t, b.cells["efuse_sense"], 0.0, -(cd_h + GAP_UM + sa_h + GAP_UM),
                    away_y=False)
    step_x = snap(round(pitch_x / DBU_UM)) * DBU_UM
    step_y = snap(round(pitch_y / DBU_UM)) * DBU_UM
    route_array_top(b, t, row_xy, rd_xy, cd_xy, sa_xy, step_x, step_y)

    verify_fuse(b.layout, "efuse_bitcell__Xf", fuse_gds)

    # gf180mcu's full deck requires the exported stream at 0.001 um per
    # database unit (its DBU rule; issue #311). The working grid stays at
    # klt's 0.0005 um -- the 0.005 um rule grid and the import rescale above
    # are stated in source dbu -- and the coarsening happens at the final
    # write: every coordinate the stream stores is even (checked; an odd one
    # is fatal), so 2:1 preserves the micron geometry exactly.
    dbu_export.coarsen(b.layout)
    opts = kdb.SaveLayoutOptions()
    opts.format = "GDS2"
    opts.gds2_write_timestamps = False
    opts.gds2_libname = "efuse_otp_array"
    b.layout.write(str(out_gds), opts)

    # Read the emitted stream back: the fuse comparison and the reported dbu
    # describe the stream that ships, not the working layout.
    emitted = kdb.Layout()
    emitted.read(str(out_gds))
    verify_fuse(emitted, "efuse_bitcell__Xf", fuse_gds)
    bb = emitted.cell(top).bbox()
    report = {
        "top_cell": top,
        "dbu_um": emitted.dbu,
        "bbox_um": [round(v * emitted.dbu, 4) for v in (bb.left, bb.bottom, bb.right, bb.top)],
        "array": {"rows": ROWS, "cols": COLS, "pitch_x_um": round(pitch_x, 4),
                  "pitch_y_um": round(pitch_y, 4)},
        "caveat": "fully routed hierarchy: all eight analog cells (efuse_bitcell, "
                  "efuse_ls, efuse_rowdrv, efuse_coldrv, efuse_comp, efuse_sense, "
                  "efuse_row and efuse_otp_array) are routed (see 'routed'); "
                  "the five fuse-free cells LVS-match their subckts under pinned "
                  "klt 0.9.2 while the three fuse-bearing cells (efuse_bitcell, "
                  "efuse_row, efuse_otp_array) carry LVS probes only -- analog "
                  "item 4 LVS signoff with recognized fuses remains with #32",
        "routed": {"cells": ["efuse_bitcell", "efuse_ls", "efuse_rowdrv", "efuse_coldrv",
                             "efuse_comp", "efuse_sense", "efuse_row", "efuse_otp_array"],
                   "planes": {"m1": "device pads, guard-ring taps and the source-ring bridge",
                              "m2": "supply rails, horizontal runs, stubs and rowdrv-to-row wl bridges",
                              "m3": "vertical stubs, lanes and local via2-to-via3 landing pads",
                              "m4": "top-level horizontal signal/supply buses, local coldrv jumpers and rowdrv vertical supply rails",
                              "m5": "top-level vertical bit-line trunks (10 um), supply trunks/feeders (10 um vss/vprog, 1.2 um vdd33) and sense drops"}},
        "program_path": {
            "claim": "path delivery only (spec section 3): no claim that the fuse "
                     "changes state or that a pulse programs it",
            "target": ">= 10 mA through the fuse at the worst corner (spec section 2, "
                      "assumption A2 and decision 0002: no PDK source)",
            "simulated": "sim/corner-verification record 20261123T205019Z-f6eeac7. "
                         "All 135 schematic points pass with 20 ohm assumed route resistance. "
                         "The minimum is 10.8722 mA at ss / 125 C / vdd33 2.97 V / "
                         "vprog 4.5 V / 260 ohm, a 0.8722 mA margin over A2.",
            "current_limits": "GF180 design manual section 14.2, tables 14.3-14.4 "
                              "(https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_14_2.html). "
                              "At 125 C the unidirectional limits are 0.67 mA/um for M1-M4, "
                              "1.21 mA/um for M5 (9000 angstrom MetalTop) and 0.18 mA per 0.26 um via. "
                              "For same-direction rectangular pulses with zero idle current, "
                              "average current equals pulse current times the duty cycle on that segment. "
                              "A2 requires 10 mA during the pulse. A3 gives pulse width only. "
                              "Applying the EM limits requires a repetition rate and current sharing.",
            "resistance_estimate": "Hand estimate from the west ends of the south M4 buses, "
                                   "vprog (-10.59, -104 um) through Xarr[31].Xb[0] "
                                   "(physical column 7, bl[0]) to vss (-16.09, -78 um). "
                                   "Direct M4 contacts exclude access metal and vias from the "
                                   "labeled M1 pins, including the single via2 and via3 at the "
                                   "sense-block vprog tap. Nominal/high PDK Magic values are "
                                   "0.09/0.104 ohm/sq on M1-M4, 0.04/0.049 ohm/sq on M5 "
                                   "and 4.5/15.0 ohm per via cut.",
            "top_segments": [
                {"net": "vprog", "segment": "south horizontal main bus",
                 "layer_width": "M4 24.0 um wide (length <= 1029 um to col 7)",
                 "vias": "via4 x36 (6x6 at 0.64 um pitch) into column feeder"},
                {"net": "vprog", "segment": "column feeder + local coldrv jumper",
                 "layer_width": "M5 10.0 um wide (61 um) -> M4 1.60 um wide jumper",
                 "vias": "via4 x20 into jumper; via3 x24 + via2 x24 onto coldrv M2 rail"},
                {"net": "vprog -> bl", "segment": "efuse_coldrv (Mdrv m=3 parallel units, constituent cell)",
                 "layer_width": "M2 0.42 um rails/tracks, 3x parallel M3 0.30 um lanes, M1 rings/straps",
                 "vias": "3 parallel units x (via2 + via2 + via1) on vprog and (via1 + via2 + via2) on bl"},
                {"net": "bl[c]", "segment": "local coldrv jumper -> vertical column trunk (to row 31)",
                 "layer_width": "M4 4.0 um wide (93 um) -> M5 10.0 um wide trunk (690 um)",
                 "vias": "via2 x12 + via3 x12 (coldrv) -> via4 x15 (trunk) -> via4 x8 + via3 x8 (per bitcell M3 lane)"},
                {"net": "vss", "segment": "row M2 tap -> vertical column return trunk (from row 31) -> south main bus",
                 "layer_width": "M2 0.42 um (~1 um from bitcell) -> M5 10.0 um trunk (779 um) -> M4 24.0 um bus (<= 999 um)",
                 "vias": "via2 x8 + via3 x8 + via4 x8 per row/col beside bitcell vss exit; via4 x36 into south bus"},
            ],
            "bitcell_segments": [
                {"net": "bl", "entry": "fuse in pad (M1, 5.295 x 0.81 um, PDK)",
                 "stack": "via1 x2 + M2 pad 0.97 x 0.42 + via2 x2 + M3 lane 0.97 wide"},
                {"net": "fuse element", "layers": "PDK primitive, geometry unmodified "
                 "(verify_fuse); not extractable as a device by the curated deck"},
                {"net": "n", "entry": "fuse out pad (M1, 4.535 x 1.75 um, PDK)",
                 "stack": "via1 x2, M2 run 6.82 x 0.42 um, via1 x3 on the 0.42 um "
                          "select drain strap"},
                {"net": "vss", "entry": "select source strap, 8.1 x 0.42 um M1",
                 "stack": "M1 bridge 1.49 x 0.42 into the guard ring, via1 x2, "
                          "M2 rail 0.42 um (row rail, tapped ~1 um east by top-level vss trunk)"},
            ],
            "finding": "The bitcell via stacks on bl, fuse out and vss contribute about "
                       "10.5/35.0 ohm nominal/high. The three parallel coldrv branches "
                       "contribute about 9.0/30.0 ohm in vias on vprog and bl. Including "
                       "local metal gives 23.55/69.67 ohm inside the cells. Top-level routes "
                       "add 21.36/33.88 ohm (rows 1, 2, 5 and 10 in layout/README.md). "
                       "The 44.91/103.55 ohm bus-to-bus interconnect estimate exceeds the "
                       "assumed 20 ohm that yielded 0.8722 mA schematic margin. Issue #407 "
                       "tracks extraction and verification of worst-corner fuse current against A2.",
        },
        "resistors": {"device": "ppolyf_u",
                      "rsh_ohm_sq": RSH_PPOLYF_U,
                      "source": "sm141064.ngspice .param rsh_ppolyf_u (350) and the "
                                "ppolyf_u model card's r_dl/r_dw deltas and its two series "
                                "terminal resistors (ppolyf_u_t, rsh 60); the netlist "
                                "states r_length/r_width and the drawn body is exactly "
                                "that geometry",
                      "note": "ohms_lvs_drawn is the deck's LVS value (drawn L/W * "
                              "rsh), which both compare sides compute from the same "
                              "geometry; ohms_sim_nominal applies the model deltas and both "
                              "terminal resistors (25 C, typical) and is what the netlist's lengths were solved for"},
        "devices": b.devices,
    }
    Path(report_json).write_text(json.dumps(report, indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--klt", required=True, help="klt argv, e.g. 'uvx --from klayout-tools==X klt'")
    ap.add_argument("--netlist", required=True)
    ap.add_argument("--pdk", required=True)
    ap.add_argument("--pdk-root", required=True)
    ap.add_argument("--fuse-gds", required=True, help="PDK libs.ref/gf180mcu_fd_pr/gds/efuse.gds")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--report", required=True)
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        klt = Klt(shlex.split(a.klt), a.pdk, a.pdk_root, tmp)
        build(a.netlist, klt, a.fuse_gds, a.output, a.report)
    print(hashlib.sha256(Path(a.output).read_bytes()).hexdigest())


if __name__ == "__main__":
    sys.exit(main())
