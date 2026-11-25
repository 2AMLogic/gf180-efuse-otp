#!/usr/bin/env python3
"""Generate layout/efuse_otp_array.gds (analog partition) from the netlist.

Run it through layout/regen-gds.sh, which supplies the pinned klt and PDK:
the interpreter must be the pinned klt's own (it provides klayout.db) and the
leaf devices are produced by that same klt (`klt gen`).

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
import math
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

import klayout.db as kdb

# klt_python -I (isolated mode) does not add this script's directory to
# sys.path; the converter module lives beside it.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dbu_export

DBU_UM = 0.0005  # the dbu `klt gen` writes for gf180mcu
GRID_DBU = 10  # the 0.005 um rule grid in database units (DBU_UM = 0.0005)
GAP_UM = 2.0  # clearance between placed cells (bboxes include guard rings)
MAX_FINGER_W_UM = 10.0  # folded devices: fingers of at most this width
# The schematic instantiates the PDK's own resistor (`XRb ... ppolyf_u
# r_width=.. r_length=..`), so the drawn body is the netlist's stated geometry.
# The numbers below are the model card's (sm141064.ngspice `.subckt ppolyf_u`):
# sheet resistance `.param rsh_ppolyf_u`, and the per-side deltas r_dl / r_dw
# the model subtracts from the drawn length / width. The deck's LVS extraction
# compares R = drawn L / drawn W * 350; the simulation model additionally
# applies the deltas, so the netlist's lengths are solved for the model's
# nominal R (2k / 400 ohm) and the drawn-geometry R the compare sees is
# recorded per device in the report.
RSH_PPOLYF_U = 350.0
PPOLYF_U_DL_UM = 4e-5  # 2 * r_dl (2e-11 m per side: r_l = r_length - 2*r_dl)
PPOLYF_U_DW_UM = 0.051  # 2 * r_dw (2.55e-8 m per side)
# The model also puts a terminal resistor (rt1, rt2: `.model ppolyf_u_t`,
# rsh 60 ohm/sq, l = 1 um, w = r_w) in series with the body at each end.
RSH_PPOLYF_U_TERM = 60.0
PPOLYF_U_TERM_L_UM = 1.0

MOS_MODELS = {
    "nfet_03v3": ("nfet", ""),
    "pfet_03v3": ("pfet", ""),
    "nfet_06v0": ("nfet", "medium_voltage"),
    "pfet_06v0": ("pfet", "medium_voltage"),
}
SUFFIX = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6}

# efuse_ls routing (see ls_cell and layout/README.md, "efuse_ls routing").
# gf180mcu GDS layer/datatype pairs (PDK tech layer table).
LS_M1, LS_M1_LBL = (34, 0), (34, 10)
LS_M2, LS_M3 = (36, 0), (42, 0)
LS_VIA1, LS_VIA2 = (35, 0), (38, 0)
LS_VIA_SIZE = 0.26  # the deck's fixed via1/via2 square (gf180mcu 7.14)
LS_PAD2 = 0.4  # M2 landing pad at every M1 connection point
LS_W1 = 0.42  # M1 routing width (pad width)
LS_W2 = 0.42  # M2 routing width (rails and strips)
LS_W3 = 0.42  # M3 routing width
LS_W3N = 0.30  # M3 width where two verticals share a device column
LS_V2_END = LS_VIA_SIZE / 2 + 0.06  # M3 end that lands a via2 reaches this far past the cut centre: on M3 narrower than 0.34 um the cut needs 0.06 um of end overlap (V2.4b) and, its side overlap below 0.04 um, 0.06 um on the adjacent edges too (V2.4c)
# End-of-line reach of a narrow (< 0.34 um) M3 lane past a via2 centre in the
# comp/sense row routing: the 0.26 um cut's half size plus the 0.06 um V2.4b
# end-of-line overlap (V2.4c is met by the same extension), rounded up to 0.20.
M3_END = 0.20
# Stated floorplan, um: bbox lower-left of each leaf, two device rows.
LS_COL_X = {"XMpi": 0.0, "XMni": 0.0, "XMp1": 6.24, "XMn1": 6.24,
            "XMp2": 12.90, "XMn2": 12.90}
LS_ROW_Y = {"XMpi": 12.0, "XMp1": 12.0, "XMp2": 12.0,
            "XMni": 0.0, "XMn1": 0.0, "XMn2": 0.0}
LS_NMOS = ("XMni", "XMn1", "XMn2")
LS_VSS_RAIL_Y = -1.5  # M2 rail below the NMOS row
LS_TRACK_Y = {"in": 8.6, "inb": 10.2, "x1": 3.23, "out": 11.0}
LS_JUNC_X = {"inb": 5.0, "x1": 11.5, "out": 12.3}  # channel-area junctions
LS_M3_HORIZ_Y = {"x1": 17.2, "out": 18.0}  # runs above the PMOS row

# efuse_coldrv routing (see coldrv_cell and layout/README.md, "efuse_coldrv routing").
SUPPLY = ("vdd33", "vprog", "vss")
CD_SHIFT = 0.16  # S lane west / D lane east of the pin, so a device's three lanes sit 0.59 um apart
CD_TRACK_PITCH = 0.72  # M2 signal tracks above the device row (0.42 um wide)
CD_RAIL_Y = {"vss": -1.5, "vdd33": -2.22, "vprog": -2.94}  # M2 supply rails below the row
CD_LANE_PITCH = 0.72  # M3 lanes added beside the efuse_ls instance
CD_LS_RAIL_END = 16.0  # east end of efuse_ls's vss rail (ls_cell)

# efuse_bitcell / efuse_row routing (bitcell_cell, array_row_cell; see
# layout/README.md, "efuse_bitcell / efuse_row routing"). All values um.
BC_SEL_X = 13.285  # select (rotated 180 deg) bbox west edge: fuse east edge + 2.005
BC_PAD_Y = 2.19  # centre y of both fuse M1 pads (asserted against the PDK cell)
BC_BL_CUT_X = (0.93, 1.48)  # two via1+via2 stacks, from the in pad's west edge
BC_BL_LANE_Y0 = -1.35  # bl M3 lane south end (crosses the wl rail below the cell)
BC_N_FUSE_CUT_DX = (-1.38, -0.38)  # via1s on the fuse out pad, from its east edge
BC_N_SEL_CUT_DX = (0.175, 0.875, 1.575)  # via1s on the drain strap, from its exit pad
BC_WL_STUB_Y0 = -1.24  # wl M2 stub down to the row rail (rail top edge)
BC_VSS_CUT_DY = (0.0, -0.55)  # two via1s on the ring east strap (0.55 >= 0.26+0.26)
BC_VSS_PAD_DY = -0.71  # M2 pad from below the lower cut to the rail top edge
ROW_WL_RAIL_Y = (-1.24, -0.82)  # M2 word-line rail under the bitcells
ROW_VSS_RAIL_Y = (7.25, 7.67)  # M2 return rail through the select row

# efuse_comp / efuse_sense routing (comp_cell, sense_cell and layout/README.md,
# "efuse_comp routing" / "efuse_sense routing"). Both cells reuse the coldrv
# planes and pitches: one row of leaf devices (efuse_comp: seven MOS; efuse_
# sense: twenty leaves and the routed efuse_comp instance among them, in
# netlist order), one via1 + M2 pad + via2 + vertical M3 lane per signal pin,
# one M2 track per multi-pin net in a channel above the row, and the M2 supply
# rails below it (same y as efuse_ls's own vss rail, so efuse_sense's rails
# merge with the efuse_comp instance's where they cross it).
CS_RAIL_Y = {"vss": -1.5, "vdd33": -2.22}  # M2 supply rails below the row
CS_EXPORT = 0.9  # efuse_comp's pin lanes extend this far above its channel

# Top-level array routing (route_array_top and layout/README.md,
# "efuse_otp_array top-level routing"). Uses the upper planes M4 (horizontal
# buses and local landing bars) and M5 (MetalTop on 5LM gf180mcuC: vertical
# bit-line, supply and signal trunks), plus short M2 word-line bridges in the
# rowdrv-to-row gap. Every subcell uses M1-M3 only, so M4/M5 are unobstructed.
TOP_VIA3, TOP_M4 = (40, 0), (46, 0)
TOP_VIA4, TOP_M5 = (41, 0), (81, 0)
TOP_VIA_PITCH = 0.64  # 0.38 um space >= 0.36 um (V2/V3/V4.2b for >=4x4 arrays)
TOP_M4_SIG_W = 0.50  # M4 signal bus width (>= 0.28 M4.1; >= 0.12 via enclosure)
TOP_M5_SIG_W = 0.80  # M5 signal drop width (>= 0.44 9K MT.1; >= 0.5625 um^2 MT.4)
TOP_TRUNK_W = 10.0  # per-column vertical M5 trunks (bl, vss, vprog; <= 10 um avoids MT.2b)
TOP_BUS_W = 24.0  # south horizontal main M4 supply buses (vss, vprog; < 30 um MSLOT.1)
TOP_VDD_BUS_W = 4.0  # south horizontal main M4 vdd33 bus
TOP_RD_RAIL_W = 2.0  # west vertical M4/M5 supply rails over efuse_rowdrv
TOP_BL_BAR_W = 4.0  # per-column horizontal M4 bl jumper over efuse_coldrv
TOP_VPROG_BAR_W = 1.60  # per-column horizontal M4 vprog jumper over efuse_coldrv
TOP_VDD_FEED_W = 1.20  # per-column vertical M5 vdd33 feeder
TOP_VSS_COL_X = (24.0, 34.0)  # column-local M5 vss trunk x span (beside bitcell vss exit)
TOP_VPROG_COL_X = (60.0, 70.0)  # column-local M5 vprog feeder x span
TOP_VDD_COL_X = 110.0  # column-local M5 vdd33 feeder centre x (M3-free over coldrv & sense)
TOP_SIG_Y = {"prog_strobe": -15.0, "sense_en": -18.0}
TOP_SA_TAP_Y = {"sense_en": -50.0, "sbl": -44.0}
TOP_BUS_Y = {"vss": (-90.0, -66.0), "vprog": (-116.0, -92.0), "vdd33": (-122.0, -118.0)}

# Expected shape of the array top, asserted against the netlist.
ROWS, COLS = 32, 8


def parse_value(text):
    m = re.fullmatch(r"([0-9.]+(?:e[+-]?[0-9]+)?)(meg|[fpnumk])?", text.strip().lower())
    if not m:
        raise ValueError(f"cannot parse value {text!r}")
    value = float(m.group(1))
    if m.group(2):
        value *= SUFFIX[m.group(2)]
    return value


def parse_netlist(path):
    """{subckt: [instance dict]} in file order; the top is the `**.subckt`."""
    lines = []
    for raw in Path(path).read_text().splitlines():
        if raw.startswith("+"):
            lines[-1] += " " + raw[1:]
        else:
            lines.append(raw)
    subckts, current = {}, None
    for line in lines:
        s = line.strip()
        m = re.match(r"\*{0,2}\.subckt\s+(\S+)", s)
        if m:
            current = subckts.setdefault(m.group(1), [])
            continue
        if re.match(r"\*{0,2}\.ends", s):
            current = None
            continue
        if current is None or not s or s.startswith("*"):
            continue
        tok = shlex.split(s)
        name = tok[0]
        if name[0] == "R":
            current.append({"kind": "res", "name": name, "ohms": parse_value(tok[3])})
            continue
        if name[0] != "X":
            raise ValueError(f"unsupported netlist line: {s[:60]}")
        plain = [t for t in tok[1:] if "=" not in t]
        params = dict(t.split("=", 1) for t in tok[1:] if "=" in t)
        current.append({"kind": "x", "name": name, "master": plain[-1], "params": params,
                        "nodes": plain[:-1]})
    return subckts


class Klt:
    def __init__(self, argv, pdk, pdk_root, workdir):
        self.argv, self.pdk, self.pdk_root, self.workdir = argv, pdk, pdk_root, workdir
        self.n = 0
        self.cache = {}

    def gen(self, generator, params):
        key = (generator, json.dumps(params, sort_keys=True))
        if key in self.cache:
            return self.cache[key]
        self.n += 1
        out = Path(self.workdir) / f"gen{self.n}.gds"
        cmd = self.argv + [
            "gen", generator, "--pdk", self.pdk, "--pdk-root", self.pdk_root,
            "--params", json.dumps(params), "--cell-name", f"leaf{self.n}",
            "-o", str(out), "--format", "json",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        report = json.loads(res.stdout)
        self.cache[key] = (str(out), report["cell_name"], report)
        return self.cache[key]


def snap(dbu, up=True):
    """Round a database-unit length to the rule grid, up or down."""
    q = -(-dbu // GRID_DBU) if up else dbu // GRID_DBU
    return q * GRID_DBU


def gs(um):
    """Snap a um coordinate to the rule grid (exact when already on it)."""
    step = GRID_DBU * DBU_UM
    return round(um / step) * step


def fold(width_um):
    fingers = max(1, math.ceil(width_um / MAX_FINGER_W_UM - 1e-9))
    return fingers, round(width_um / fingers, 6)


class Builder:
    def __init__(self, klt, fuse_gds, netlist):
        self.klt, self.fuse_gds = klt, fuse_gds
        self.netlist = netlist
        self.layout = kdb.Layout()
        self.layout.dbu = DBU_UM
        self.cells = {}
        self.reports = {}  # leaf cell name -> that leaf's klt gen JSON report
        self.devices = []  # report rows
        self.anchor = {}  # leaf cell index -> pre-growth bbox (footprint)

    def import_cell(self, gds, src_name, dst_name):
        src = kdb.Layout()
        src.read(gds)
        if abs(src.dbu - DBU_UM) > 1e-12:
            ratio = src.dbu / DBU_UM
            assert abs(ratio - round(ratio)) < 1e-9, "dbu ratio must be an integer"
            src.transform(kdb.ICplxTrans(float(round(ratio))))
            src.dbu = DBU_UM
        before = {c.cell_index() for c in self.layout.each_cell()}
        dst = self.layout.create_cell(dst_name)
        dst.copy_tree(src.cell(src_name))
        for c in list(self.layout.each_cell()):
            if c.cell_index() not in before and c.cell_index() != dst.cell_index():
                c.name = f"{dst_name}_{c.name.split('$')[0]}"
        return dst

    def leaf(self, subckt, inst):
        name = f"{subckt}__{inst['name'][1:]}"
        if inst["kind"] == "res":
            raise ValueError(
                f"{inst['name']}: ideal R cards are not drawn; instantiate the "
                "PDK resistor (ppolyf_u) in the schematic instead")
        master = inst["master"]
        if master == "ppolyf_u":
            # The netlist states the drawn geometry (r_length/r_width, metres);
            # the strip is generated at exactly those dimensions, so the deck's
            # LVS value (drawn L / drawn W * rsh) and the reference conversion's
            # agree by construction.
            w = round(parse_value(inst["params"]["r_width"]) * 1e6, 6)
            length = round(parse_value(inst["params"]["r_length"]) * 1e6, 6)
            gds, top, report = self.klt.gen("res_array", {
                "length_um": length, "width_um": w, "num": 1,
                "dummy": 0, "flavor": "generic"})
            self.reports[name] = report
            self.devices.append({"cell": name, "device": "ppolyf_u",
                                 "r_length_um": length, "r_width_um": w,
                                 "ohms_lvs_drawn": round(length / w * RSH_PPOLYF_U, 2),
                                 "ohms_sim_nominal": round(
                                     ((length - PPOLYF_U_DL_UM) * RSH_PPOLYF_U
                                      + 2 * PPOLYF_U_TERM_L_UM * RSH_PPOLYF_U_TERM)
                                     / (w - PPOLYF_U_DW_UM), 2)})
            cell = self.import_cell(gds, top, name)
            self.grow_resistor_implants(cell)
            return cell
        if master == "efuse":
            # The PDK primitive, copied as-is (only its dbu is rescaled by an
            # exact integer); not routed through any generator.
            self.devices.append({"cell": name, "device": "efuse", "source": "PDK efuse.gds"})
            return self.import_cell(self.fuse_gds, "efuse_cell", name)
        flavor, vflavor = MOS_MODELS[master]
        w = round(parse_value(inst["params"]["W"]) * 1e6, 6)
        l = round(parse_value(inst["params"]["L"]) * 1e6, 6)
        fingers, wf = fold(w)
        gds, top, report = self.klt.gen("mos_array", {
            "w_um": wf, "l_um": l, "fingers": fingers, "rows": 1, "cols": 1,
            "dummy": 0, "topology": "array", "flavor": flavor,
            "voltage_flavor": vflavor, "gate_contact": True, "add_guard_ring": True})
        self.reports[name] = report
        row = {"cell": name, "device": master, "w_um": w, "l_um": l,
               "fingers": fingers, "finger_w_um": wf}
        m = int(inst["params"].get("m", "1"))
        if m > 1:
            row["m"] = m  # drawn as m placed units of this cell (coldrv_cell)
        self.devices.append(row)
        cell = self.import_cell(gds, top, name)
        if (flavor, vflavor) == ("pfet", "medium_voltage"):
            self.grow_mv_pmos_wells(cell)
        return cell

    # The generated 6 V PMOS guard ring (N+ COMP in Nwell, under Dualgate) is
    # drawn with Nwell 0.15 um and Dualgate 0.13 um beyond the ring COMP; the
    # deck wants Nwell overlap of NCOMP >= 0.16 um (DF.4d_MV) and Dualgate
    # enclosure of COMP >= 0.24 um (DV.6). Grow both over the whole cell.
    NWELL_LAYER, DUALGATE_LAYER = (21, 0), (55, 0)
    NWELL_GROW_UM, DUALGATE_GROW_UM = 0.01, 0.12

    # The generated ppolyf_u body has Pplus only over the body and salicide
    # block 0.22 um past the poly in width. The deck's resistor is poly under
    # Pplus, SAB and RES_MK: PRES.5/PP.9 want Pplus >= 0.3 um beyond it, PRES.6
    # wants SAB >= 0.28 um past it in width, SB.13 wants SAB area >= 2 um^2.
    POLY_LAYER, PPLUS_LAYER, SAB_LAYER = (30, 0), (31, 0), (49, 0)
    CONTACT_LAYER, CONTACT_SAB_SPACE_UM, CONTACT_POLY_ENC_UM = (33, 0), 0.22, 0.07
    PPLUS_GROW_UM, SAB_MIN_GROW_UM, SAB_MIN_AREA_UM2 = 0.3, 0.28, 2.0

    def grow_resistor_implants(self, cell):
        self.anchor[cell.cell_index()] = cell.bbox()
        idx = {k: self.layout.find_layer(*k)
               for k in (self.POLY_LAYER, self.PPLUS_LAYER, self.SAB_LAYER)}
        for k, v in idx.items():
            if v is None:
                raise ValueError(f"{cell.name}: layer {k} missing from the generated resistor")
        poly = kdb.Region(cell.begin_shapes_rec(idx[self.POLY_LAYER]))
        sab = kdb.Region(cell.begin_shapes_rec(idx[self.SAB_LAYER]))
        pb, sb = poly.bbox(), sab.bbox()
        g = round(self.PPLUS_GROW_UM / DBU_UM)
        cell.shapes(idx[self.PPLUS_LAYER]).insert(
            kdb.Box(pb.left - g, pb.bottom - g, pb.right + g, pb.top + g))
        # SAB: widen across the body (y, the width direction) until both the
        # overlap and the area minimum hold, on the rule grid.
        need_um = max(self.SAB_MIN_GROW_UM,
                      (self.SAB_MIN_AREA_UM2 / (sb.width() * DBU_UM) - pb.height() * DBU_UM) / 2)
        gy = snap(math.ceil(need_um / DBU_UM - 1e-9))
        cell.shapes(idx[self.SAB_LAYER]).insert(
            kdb.Box(sb.left, pb.bottom - gy, sb.right, pb.top + gy))
        # PRES.7: head contacts must sit >= 0.22 um from the SAB (the generated
        # ones sit 0.15 um). Slide each outward; the poly keeps >= 0.07 um
        # (CO.5a) of enclosure past it, asserted.
        cli = self.layout.find_layer(*self.CONTACT_LAYER)
        if cli is None:
            raise ValueError(f"{cell.name}: contact layer missing from the generated resistor")
        # import_cell leaves the generated shapes in an unrotated, unshifted
        # child of the returned cell; the slide edits them where they live.
        for sub in [cell] + [self.layout.cell(i) for i in cell.called_cells()]:
            shapes = sub.shapes(cli)
            for sh in list(shapes.each()):
                b = sh.bbox()
                if b.right <= sb.left:
                    shift = -snap(max(0, round(self.CONTACT_SAB_SPACE_UM / DBU_UM) - (sb.left - b.right)))
                elif b.left >= sb.right:
                    shift = snap(max(0, round(self.CONTACT_SAB_SPACE_UM / DBU_UM) - (b.left - sb.right)))
                else:
                    raise ValueError(f"{cell.name}: contact {b} sits under the SAB")
                moved = b.moved(shift, 0)
                if min(moved.left - pb.left, pb.right - moved.right) < round(self.CONTACT_POLY_ENC_UM / DBU_UM):
                    raise ValueError(f"{cell.name}: sliding the contact leaves <0.07 um of poly enclosure")
                shapes.erase(sh)
                shapes.insert(moved)

    def grow_mv_pmos_wells(self, cell):
        self.anchor[cell.cell_index()] = cell.bbox()
        for (lay, dt), grow in ((self.NWELL_LAYER, self.NWELL_GROW_UM),
                                (self.DUALGATE_LAYER, self.DUALGATE_GROW_UM)):
            li = self.layout.find_layer(lay, dt)
            if li is None:
                raise ValueError(f"{cell.name}: layer {lay}/{dt} missing from the generated cell")
            reg = kdb.Region(cell.begin_shapes_rec(li)).sized(round(grow / DBU_UM))
            cell.shapes(li).insert(reg)

    def footprint(self, cell):
        """A leaf's drawn extent before grow_resistor_implants /
        grow_mv_pmos_wells widened its implants: the extent y placement (and
        nothing that steps a cursor) is floorplanned against."""
        return self.anchor.get(cell.cell_index(), cell.bbox())

    def place(self, parent, child, x_um, y_um, rows=1, cols=1, pitch_x_um=0.0, pitch_y_um=0.0,
              away_x=True, away_y=True, rot=0):
        """Instance of child with its (rotated) grown bbox left at x_um and its
        (rotated) footprint bottom at y_um, snapped.

        rot is a klayout rotation index (0..3, no mirroring; 2 = 180 deg) --
        the bbox is rotated first and its lower-left landed on the rule grid,
        exactly as for rot=0. x anchors on the grown bbox().left -- the same
        extent every row cursor steps on -- so the grown-to-grown separation is
        GAP_UM whatever each neighbour's west overhang (#376); y stays on the
        pre-growth footprint, which no cursor steps on. The child's bbox edges
        are vertices (guard rings; the PDK fuse stream's own origin is off the
        grid by one stream dbu), so landing them on the rule grid puts every
        vertex on it. Both edges are rounded away from the placed neighbours
        (up, or down with away_* False) so the clearance is never reduced; the
        pitches are rounded up to the grid. Returns the applied displacement in
        um: port tables computed from the child's own reported coordinates must
        add it (after any rotation) to land on the drawn pads.
        """
        rot_t = kdb.Trans(rot, False, 0, 0)
        dx = snap(round(x_um / DBU_UM), away_x) - child.bbox().transformed(rot_t).left
        dy = snap(round(y_um / DBU_UM), away_y) - self.footprint(child).transformed(rot_t).bottom
        trans = kdb.Trans(rot, False, dx, dy)
        if rows == 1 and cols == 1:
            parent.insert(kdb.CellInstArray(child.cell_index(), trans))
        else:
            assert rot == 0, "array placement with rotation is not needed yet"
            parent.insert(kdb.CellInstArray(
                child.cell_index(), trans,
                kdb.Vector(snap(round(pitch_x_um / DBU_UM)), 0),
                kdb.Vector(0, snap(round(pitch_y_um / DBU_UM))), cols, rows))
        return dx * DBU_UM, dy * DBU_UM

    def size(self, cell):
        """A composite cell's extent for the top-level floorplan. Refuses a
        grown leaf (an anchor entry) outright: place() anchors x on the grown
        bbox (#379), so a pre-growth width handed out here and stepped into
        a cursor would re-create #376 -- every cursor steps on bbox()."""
        assert cell.cell_index() not in self.anchor, \
            f"{cell.name}: size() takes composite cells only; a grown leaf's " \
            "pre-growth width must not step a cursor -- use bbox()"
        bb = self.footprint(cell)
        return bb.width() * DBU_UM, bb.height() * DBU_UM

    def row_cell(self, subckt):
        """A subcircuit as one left-to-right row of its leaf and sub-cells."""
        cell = self.layout.create_cell(subckt)
        x = 0.0
        for inst in self.netlist[subckt]:
            child = (self.cells[inst["master"]] if inst["kind"] == "x" and inst["master"] in self.netlist
                     else self.leaf(subckt, inst))
            self.place(cell, child, x, 0.0)
            # Both sides on the grown extent: place() lands child.bbox().left
            # at x (as _row_place_all's units do), and the cursor steps on
            # child.bbox().width(), so the grown-to-grown separation keeps
            # GAP_UM whatever each neighbour's overhang (#376).
            x += child.bbox().width() * DBU_UM + GAP_UM + GRID_DBU * DBU_UM  # snap slack
        self.cells[subckt] = cell
        return cell

    # -- efuse_bitcell: fuse + select, all four nets drawn ---------------

    def bitcell_cell(self, subckt):
        """efuse_bitcell: the PDK fuse and the rotated select NFET, routed.

        Floorplan (um, this cell's own coordinates): the fuse at the origin
        (bbox 11.28 x 4.38, PDK geometry untouched, `verify_fuse` guards it);
        the select NFET east of it rotated 180 deg, so its 0.42 um drain
        strap exit faces west at the same height as the fuse out pad --
        `n` is then one M2 run over the gap: via1 x2 on the out pad, via1 x3
        along the strap (the program current crosses the pad/strap metal, the
        cuts sit between them east of the EFUSE_MK box, which M2 must not
        cross). `bl` leaves the fuse in pad on a 0.97 um M3 lane running
        south out of the cell (over the fuse only M3 may run: EF.18/19),
        stacked via1+via2 twice under it. `wl` drops from the gate pad to
        the row's M2 rail below the cell. The source strap is merged into
        its own guard ring with an M1 bridge (source and body are both vss,
        as in ls_cell) and the ring leaves east through two via1s into the
        row's M2 return rail. The fuse cell's own 'in'/'out' 34/10 texts
        are dropped: they would rename the bl/n pad nets at extraction
        (verify_fuse compares geometry; its Region sides ignore texts).
        """
        insts = {i["name"]: i for i in self.netlist[subckt]}
        assert set(insts) == {"XXf", "XXsel"}, f"{subckt} netlist changed: {sorted(insts)}"
        f, s = insts["XXf"], insts["XXsel"]
        assert f["kind"] == "x" and f["master"] == "efuse" and f["nodes"] == ["bl", "n"], \
            f"{subckt}: XXf is no longer 'bl n efuse'"
        assert s["kind"] == "x" and s["master"] == "nfet_06v0" \
            and s["nodes"] == ["n", "wl", "vss", "vss"], \
            f"{subckt}: XXsel is no longer 'n wl vss vss nfet_06v0'"
        cell = self.layout.create_cell(subckt)
        for pair in (LS_M2, LS_VIA1, LS_M3, LS_VIA2):
            self.layout.layer(*pair)

        # fuse: bbox lower-left at the origin; the two M1 pad boxes and the
        # 'in'/'out' texts are read from the imported PDK cell itself.
        fuse = self.leaf(subckt, f)
        lbl_i, m1_i = self.layout.layer(*LS_M1_LBL), self.layout.layer(*LS_M1)
        pads = {}
        for t in list(fuse.shapes(lbl_i).each()):
            p = t.text.trans.disp
            for b in fuse.shapes(m1_i).each():
                if b.box.contains(p):
                    pads[t.text.string] = b.box
            fuse.shapes(lbl_i).erase(t)
        assert set(pads) == {"in", "out"}, "PDK fuse cell must carry in/out pad texts"
        dx0, dy0 = self.place(cell, fuse, 0.0, 0.0)
        t0 = kdb.Trans(round(dx0 / DBU_UM), round(dy0 / DBU_UM))
        pin, pout = pads["in"].transformed(t0), pads["out"].transformed(t0)
        yc = pin.center().y * DBU_UM
        assert abs(yc - BC_PAD_Y) < 1e-9 and abs(pout.center().y * DBU_UM - yc) < 1e-9, \
            "fuse M1 pads no longer share a centre height"

        # select, rotated 180 deg: U0_D faces west at pad height, U0_G exits
        # south, TAP_W is the ring's east strap.
        sel = self.leaf(subckt, s)
        rep = self.reports[f"{subckt}__Xsel"]
        dx1, dy1 = self.place(cell, sel, BC_SEL_X, 0.0, rot=2)
        t1 = kdb.Trans(2, False, round(dx1 / DBU_UM), round(dy1 / DBU_UM))

        def port(name):
            p = next(p for p in rep["ports"] if p["name"] == name)
            v = t1 * kdb.Point(round(p["x_um"] / DBU_UM), round(p["y_um"] / DBU_UM))
            return gs(v.x * DBU_UM), gs(v.y * DBU_UM)

        d, g, se, tw = port("U0_D"), port("U0_G"), port("U0_S"), port("TAP_W")
        assert abs(d[1] - 2.26) < 1e-9 and abs(d[1] - yc) <= 0.075, \
            "select drain strap no longer faces the fuse out pad"

        # n: five via1s under one M2 run from the out pad to the drain strap.
        nx = [gs(pout.right * DBU_UM + dx) for dx in BC_N_FUSE_CUT_DX] \
            + [gs(d[0] + dx) for dx in BC_N_SEL_CUT_DX]
        for x in nx:
            self._cut(cell, LS_VIA1, x, BC_PAD_Y)
        self._box(cell, LS_M2, min(nx) - 0.21, BC_PAD_Y - 0.21, max(nx) + 0.21, BC_PAD_Y + 0.21)
        # bl: two via1+via2 stacks on the in pad's west end (west of the
        # EFUSE_MK box, which M1/M2 must not cross), one 0.97 um M3 lane
        # south out of the cell under them.
        bcx = [gs(pin.left * DBU_UM + x) for x in BC_BL_CUT_X]
        for x in bcx:
            self._cut(cell, LS_VIA1, x, BC_PAD_Y)
            self._cut(cell, LS_VIA2, x, BC_PAD_Y)
        self._box(cell, LS_M2, bcx[0] - 0.21, BC_PAD_Y - 0.21, bcx[-1] + 0.21, BC_PAD_Y + 0.21)
        self._box(cell, LS_M3, bcx[0] - 0.21, BC_BL_LANE_Y0, bcx[-1] + 0.21, BC_PAD_Y + 0.21)
        # wl: via1 on the gate pad, M2 stub down to the row rail.
        self._cut(cell, LS_VIA1, g[0], g[1])
        self._box(cell, LS_M2, g[0] - 0.21, BC_WL_STUB_Y0, g[0] + 0.21, g[1] + 0.21)
        # vss: M1 bridge source strap -> ring, then two via1s on the ring's
        # east strap into an M2 pad at the row rail height.
        self._box(cell, LS_M1, se[0] - 0.21, se[1] - 0.21, tw[0] + 0.21, se[1] + 0.21)
        ry = sum(ROW_VSS_RAIL_Y) / 2
        for dy in BC_VSS_CUT_DY:
            self._cut(cell, LS_VIA1, tw[0], gs(ry + dy))
        self._box(cell, LS_M2, tw[0] - 0.21, gs(ry + BC_VSS_PAD_DY),
                  tw[0] + 0.21, ROW_VSS_RAIL_Y[1])

        for net, x, y in (("bl", (bcx[0] + bcx[-1]) / 2, BC_PAD_Y),
                          ("n", pout.center().x * DBU_UM, BC_PAD_Y),
                          ("wl", g[0], g[1]), ("vss", tw[0], ry)):
            self._label(cell, net, gs(x), gs(y))
        # pin access points for the row and top-level routing (array_row_cell,
        # #307): the bl lane, the wl stub and the vss pad, all in-cell coords.
        self.bc_ports = {"bl": ((bcx[0] + bcx[-1]) / 2, BC_PAD_Y), "wl": g, "vss": (tw[0], ry)}
        self.cells[subckt] = cell
        return cell

    def array_row_cell(self, pitch_x):
        """efuse_row: 8 bitcells at the column pitch plus the shared rails.

        One M2 wl rail below the bitcells (each gate stub drops into it) and
        one M2 vss rail through the select row (each bitcell's ring-east
        via1s land on it); both span the full row and exit west. The eight
        bl lanes are the bitcells' own M3 lanes, one per column, already
        crossing the wl rail on M3; bl[7] is the west-most column, matching
        the .subckt pin order (bl[7] first). Labels sit on M1 pads of the
        first bitcell's instances (wl, vss) and on each column's fuse in
        pad (bl[i]).
        """
        assert hasattr(self, "bc_ports"), "bitcell_cell must run before array_row_cell"
        cell = self.layout.create_cell("efuse_row")
        bit = self.cells["efuse_bitcell"]
        # Identity placement (target = the bitcell's own bbox origin, which is
        # on the grid): the rails below are stated in bitcell coordinates, so
        # the instances must not be shifted to a different origin.
        bb = bit.bbox()
        assert bb.left == 0, f"efuse_bitcell bbox left {bb.left} != 0"
        self.place(cell, bit, bb.left * DBU_UM, bb.bottom * DBU_UM, 1, COLS, pitch_x)
        w = gs((COLS - 1) * pitch_x + self.size(bit)[0])
        self._box(cell, LS_M2, 0.0, ROW_WL_RAIL_Y[0], w, ROW_WL_RAIL_Y[1])
        self._box(cell, LS_M2, 0.0, ROW_VSS_RAIL_Y[0], w, ROW_VSS_RAIL_Y[1])
        bp = self.bc_ports
        self._label(cell, "wl", bp["wl"][0], bp["wl"][1])
        self._label(cell, "vss", bp["vss"][0], bp["vss"][1])
        for k in range(COLS):
            self._label(cell, f"bl[{COLS - 1 - k}]", gs(bp["bl"][0] + k * pitch_x), bp["bl"][1])
        self.cells["efuse_row"] = cell
        return cell

    # -- efuse_ls: routed two-row floorplan ------------------------------

    def ls_cell(self, subckt):
        """efuse_ls on a stated two-row floorplan, with drawn routing.

        Floorplan (um, this cell's own coordinates): NMOS row at y=0
        (XMni x=0, XMn1 x=6.24, XMn2 x=12.90), PMOS row at y=12.0 (XMpi,
        XMp1, XMp2 at the same three column origins) -- the input inverter
        in column 0, the two cross-coupled 6 V inverters in columns 1 and 2,
        so the 3.3 V pair and the 6 V quad each stay in one row and each
        column keeps a device's source, drain and gate pads vertically
        aligned. Routing: M1 device pads and guard-ring taps; M2 horizontal
        (supply rails, per-net channel runs); M3 vertical (per-pad stubs);
        0.26 um via1/via2 cuts on 0.4 um M2 landing pads. Every source pad
        is merged into its own guard ring with an M1 bridge (source and body
        are one net on each device), and each ring leaves the island at one
        tap: TAP_S for the NMOS row and the 6 V PMOS pair (both to wires in
        the channel or below it), TAP_W for XMpi (vdd33 exits west).
        """
        insts = {i["name"]: i for i in self.netlist[subckt]}
        expected = {"XMpi", "XMni", "XMn1", "XMn2", "XMp1", "XMp2"}
        assert set(insts) == expected, f"efuse_ls netlist changed: {sorted(insts)}"
        cell = self.layout.create_cell(subckt)
        ports = {}
        for iname, inst in insts.items():
            child = self.leaf(subckt, inst)
            rep = self.reports[f"{subckt}__{iname[1:]}"]
            col, row = LS_COL_X[iname], LS_ROW_Y[iname]
            dx, dy = self.place(cell, child, col, row)
            ports[iname] = {p["name"]: (gs(dx + p["x_um"]), gs(dy + p["y_um"]),
                                        p["width_um"], p["direction_deg"])
                            for p in rep["ports"]}
        # Create the routing layers before any shape is drawn, in the order
        # the committed GDS was first written with: klayout emits each cell's
        # shapes in layer-index order, and a layer's index is fixed by the
        # first draw that touches it, so without this the stream bytes would
        # depend on which helper happens to draw first (same geometry,
        # different file).
        for pair in (LS_M2, LS_VIA1, LS_M3, LS_VIA2):
            self.layout.layer(*pair)
        self._ls_supplies(cell, ports)
        self._ls_signals(cell, ports)
        self._ls_labels(cell, ports)
        self.ls_ports = ports
        self.cells[subckt] = cell
        return cell

    def _ls_supplies(self, cell, ports):
        rail = LS_VSS_RAIL_Y
        # vss: rail below the NMOS row; one tap stub per NMOS ring.
        self._box(cell, LS_M2, 0.9, rail - LS_W2 / 2, 16.0, rail + LS_W2 / 2)
        for iname in LS_NMOS:
            s, tw, ts = ports[iname]["U0_S"], ports[iname]["TAP_W"], ports[iname]["TAP_S"]
            self._box(cell, LS_M1, tw[0] - LS_W1 / 2, s[1] - s[2] / 2, s[0] - LS_W1 / 2, s[1] + s[2] / 2)
            self._cut(cell, LS_VIA1, ts[0], ts[1])
            self._box(cell, LS_M2, ts[0] - LS_W2 / 2, rail - LS_W2 / 2,
                      ts[0] + LS_W2 / 2, ts[1] + LS_W2 / 2)
        # vdd33: XMpi only; TAP_W exits west to a short open-ended stub.
        s, tw, _ = ports["XMpi"]["U0_S"], ports["XMpi"]["TAP_W"], ports["XMpi"]["TAP_S"]
        self._box(cell, LS_M1, tw[0] - LS_W1 / 2, s[1] - s[2] / 2, s[0] - LS_W1 / 2, s[1] + s[2] / 2)
        self._cut(cell, LS_VIA1, tw[0], tw[1])
        self._box(cell, LS_M2, -1.2, tw[1] - LS_W2 / 2, tw[0] + LS_W2 / 2, tw[1] + LS_W2 / 2)
        # vprog: the 6 V PMOS pair; TAP_S of both rings, joined in the channel top.
        ts1, ts2 = ports["XMp1"]["TAP_S"], ports["XMp2"]["TAP_S"]
        for iname, ts in (("XMp1", ts1), ("XMp2", ts2)):
            s, tw = ports[iname]["U0_S"], ports[iname]["TAP_W"]
            self._box(cell, LS_M1, tw[0] - LS_W1 / 2, s[1] - s[2] / 2, s[0] - LS_W1 / 2, s[1] + s[2] / 2)
            self._cut(cell, LS_VIA1, ts[0], ts[1])
        self._box(cell, LS_M2, ts1[0] - LS_W2 / 2, ts1[1] - LS_W2 / 2,
                  ts2[0] + LS_W2 / 2, ts1[1] + LS_W2 / 2)

    def _ls_signals(self, cell, ports):
        ni, pi, n1, p1, n2, p2 = (ports[n] for n in
                                  ("XMni", "XMpi", "XMn1", "XMp1", "XMn2", "XMp2"))
        # in: XMni.G <-> XMpi.G straight up column 0; branch west-to-east on
        # M2 to XMn1.G, down a short M3 stub.
        g_ni, g_pi, g_n1 = ni["U0_G"], pi["U0_G"], n1["U0_G"]
        self._ls_pad3(cell, g_ni)
        self._ls_pad3(cell, g_pi)
        self._ls_vstrip(cell, g_ni[0], g_ni[1], g_pi[1], LS_W3)
        y = LS_TRACK_Y["in"]
        self._cut(cell, LS_VIA2, g_ni[0], y)
        self._box(cell, LS_M2, g_ni[0] - LS_W2 / 2, y - LS_W2 / 2, g_n1[0] + LS_W2 / 2, y + LS_W2 / 2)
        self._ls_vstrip(cell, g_n1[0], g_n1[1], y, LS_W3)
        self._cut(cell, LS_VIA2, g_n1[0], y)
        self._ls_pad3(cell, g_n1)
        # inb: XMni.D east on M2 at pad height, M3 up the col0/col1 gap to the
        # channel track, east to XMn2.G, down a stub; XMpi.D east on M2 at pad
        # height to the same M3 (the two legs meet the track at one junction).
        d_ni, d_pi, g_n2 = ni["U0_D"], pi["U0_D"], n2["U0_G"]
        jx = LS_JUNC_X["inb"]
        yt = LS_TRACK_Y["inb"]
        self._ls_pad3(cell, d_ni, via2=False)
        self._box(cell, LS_M2, d_ni[0], d_ni[1] - LS_W2 / 2, jx + LS_W2 / 2, d_ni[1] + LS_W2 / 2)
        self._ls_vstrip(cell, jx, d_ni[1], d_pi[1], LS_W3)
        self._cut(cell, LS_VIA2, jx, d_ni[1])
        self._ls_pad3(cell, d_pi, via2=False)
        self._box(cell, LS_M2, d_pi[0], d_pi[1] - LS_W2 / 2, jx + LS_W2 / 2, d_pi[1] + LS_W2 / 2)
        self._cut(cell, LS_VIA2, jx, d_pi[1])
        self._box(cell, LS_M2, jx - LS_W2 / 2, yt - LS_W2 / 2, g_n2[0] + LS_W2 / 2, yt + LS_W2 / 2)
        self._cut(cell, LS_VIA2, jx, yt)
        self._ls_vstrip(cell, g_n2[0], g_n2[1], yt, LS_W3)
        self._cut(cell, LS_VIA2, g_n2[0], yt)
        self._ls_pad3(cell, g_n2)
        # x1: XMn1.D east on M2 at pad height, M3 up the col1/col2 gap; XMp1.D
        # taps that M3 through an M2 run at pad height; on top an M3 run east
        # drops into XMp2.G.
        d_n1, d_p1, g_p2 = n1["U0_D"], p1["U0_D"], p2["U0_G"]
        jx = LS_JUNC_X["x1"]
        yh = LS_M3_HORIZ_Y["x1"]
        self._ls_pad3(cell, d_n1, via2=False)
        self._box(cell, LS_M2, d_n1[0], d_n1[1] - LS_W2 / 2, jx + LS_W3N / 2, d_n1[1] + LS_W2 / 2)
        self._ls_vstrip(cell, jx, d_n1[1], yh, LS_W3N, land0=True)
        self._cut(cell, LS_VIA2, jx, d_n1[1])
        self._box(cell, LS_M2, d_p1[0], d_p1[1] - LS_W2 / 2, jx + LS_W3N / 2, d_p1[1] + LS_W2 / 2)
        self._cut(cell, LS_VIA2, jx, d_p1[1])
        self._ls_pad3(cell, d_p1, via2=False)
        # The top run's east end stops at the drop leg's far edge (not its own
        # half-width past the junction): one more 0.06 um would close the gap
        # to the `out` vertical at XMp2.D+0.06 below 0.28 um.
        self._ls_hstrip(cell, jx, g_p2[0] + LS_W3N / 2 - LS_W3 / 2, yh, LS_W3)
        self._ls_vstrip(cell, g_p2[0], g_p2[1], yh, LS_W3N, land0=True)
        self._ls_pad3(cell, g_p2)
        # out: XMn2.D west on M2 at pad height, M3 up to the channel, east on
        # M2, M3 up past XMp2.D (tapped there) to a top M3 run that drops west
        # into XMp1.G. XMp2.D's M1 pad centre is 0.06 um west of the column's
        # free M3 x (XMp1.D pads XMn1.D by 0.2 um), so the tap's via stack sits
        # at pad+0.06: still inside the 0.42 um pad, and 0.30 um clear of the
        # x1 stub that drops into XMp2.G.
        d_n2, d_p2, g_p1 = n2["U0_D"], p2["U0_D"], p1["U0_G"]
        jx = LS_JUNC_X["out"]
        mx = d_p2[0] + 0.06  # M3 x through XMp2.D
        ym, yh = LS_TRACK_Y["out"], LS_M3_HORIZ_Y["out"]
        self._ls_pad3(cell, d_n2, via2=False)
        self._box(cell, LS_M2, jx - LS_W3N / 2, d_n2[1] - LS_W2 / 2, d_n2[0], d_n2[1] + LS_W2 / 2)
        self._ls_vstrip(cell, jx, d_n2[1], ym, LS_W3N, land0=True, land1=True)
        self._cut(cell, LS_VIA2, jx, d_n2[1])
        self._box(cell, LS_M2, jx - LS_W3N / 2, ym - LS_W2 / 2, mx + LS_W3N / 2, ym + LS_W2 / 2)
        self._cut(cell, LS_VIA2, jx, ym)
        self._ls_vstrip(cell, mx, ym, yh, LS_W3N, land0=True)
        self._cut(cell, LS_VIA2, mx, ym)
        self._ls_pad3(cell, d_p2, via2_x=mx)
        self._ls_hstrip(cell, g_p1[0], mx, yh, LS_W3)
        self._ls_vstrip(cell, g_p1[0], g_p1[1], yh, LS_W3N, land0=True)
        self._ls_pad3(cell, g_p1)

    def _ls_labels(self, cell, ports):
        lbl = self.layout.layer(*LS_M1_LBL)
        for net, iname, port in (("in", "XMni", "U0_G"), ("inb", "XMni", "U0_D"),
                                 ("x1", "XMn1", "U0_D"), ("out", "XMn2", "U0_D"),
                                 ("vdd33", "XMpi", "TAP_W"), ("vprog", "XMp1", "TAP_S"),
                                 ("vss", "XMn1", "TAP_S")):
            x, y = ports[iname][port][0], ports[iname][port][1]
            text = kdb.Text(net, kdb.Trans(round(x / DBU_UM), round(y / DBU_UM)))
            cell.shapes(lbl).insert(text)

    def _ls_pad3(self, cell, port, via2_x=None, via2=True):
        """via1 + M2 landing pad + via2 at one M1 pad centre.

        via2_x shifts only the upper cut (M2 pad still centres on the M1
        pad): used where the M3 stub through a 0.42 um pad must clear a
        neighbouring net's M3 by 0.28 um (XMp2.D). via2=False omits the cut
        where the net's M3 does not run over this pad (the D pads: their M2
        runs to the junction, which carries its own via2); a cut with no M3
        above it is an unlanded via (V2.3c/d, V2.4b/c: unmodeled in the deck,
        gated by layout/check_via2_landing.sh).
        """
        cx, cy = port[0], port[1]
        h = LS_PAD2 / 2
        self._cut(cell, LS_VIA1, cx, cy)
        self._box(cell, LS_M2, cx - h, cy - h, cx + h, cy + h)
        if via2:
            self._cut(cell, LS_VIA2, via2_x if via2_x is not None else cx, cy)

    def _ls_vstrip(self, cell, x, y0, y1, w, land0=False, land1=False):
        """Vertical M3 strip between two endpoints, a w/2 shoulder past each
        end. land0/land1 mark an end whose endpoint centres a via2 cut: that
        shoulder alone leaves w/2 - 0.13 um of end overlap (0.02 um on
        LS_W3N), so the strip reaches LS_V2_END past the endpoint instead."""
        # Each land flag stays with its own endpoint whichever order the
        # caller passes them in: sort (y, flag) pairs, not the bare ys.
        (lo, land_lo), (hi, land_hi) = sorted([(y0, land0), (y1, land1)],
                                              key=lambda p: p[0])
        e = max(0.0, LS_V2_END - w / 2)
        self._box(cell, LS_M3, x - w / 2, lo - w / 2 - (e if land_lo else 0.0),
                  x + w / 2, hi + w / 2 + (e if land_hi else 0.0))

    def _ls_hstrip(self, cell, x0, x1, y, w):
        lo, hi = min(x0, x1), max(x0, x1)
        self._box(cell, LS_M3, lo - w / 2, y - w / 2, hi + w / 2, y + w / 2)

    # -- boxes, cuts and labels shared by efuse_ls and the driver cells ----

    def _box(self, cell, pair, x0, y0, x1, y1):
        li = self.layout.layer(*pair)
        cell.shapes(li).insert(kdb.Box(round(gs(x0) / DBU_UM), round(gs(y0) / DBU_UM),
                                       round(gs(x1) / DBU_UM), round(gs(y1) / DBU_UM)))

    def _cut(self, cell, pair, cx, cy):
        h = LS_VIA_SIZE / 2
        self._box(cell, pair, cx - h, cy - h, cx + h, cy + h)

    # -- efuse_rowdrv / efuse_coldrv: routed from efuse_ls and leaf devices --

    def _label(self, cell, net, x, y):
        cell.shapes(self.layout.layer(*LS_M1_LBL)).insert(
            kdb.Text(net, kdb.Trans(round(x / DBU_UM), round(y / DBU_UM))))

    def _stack(self, cell, x, y, lane_x=None, via2=True):
        """via1 + M2 landing pad at an M1 point, via2 at lane_x (the M2 pad
        stretches from the point to the lane so the M3 lane can sit off the pin).
        via2=False leaves the cut to the caller, which draws it only once an M3
        lane lands on it."""
        lx = x if lane_x is None else lane_x
        h = LS_PAD2 / 2
        self._cut(cell, LS_VIA1, x, y)
        self._box(cell, LS_M2, min(x, lx) - h, y - h, max(x, lx) + h, y + h)
        if via2:
            self._cut(cell, LS_VIA2, lx, y)

    def rowdrv_cell(self, subckt):
        """efuse_rowdrv: the routed efuse_ls instance at the origin; the five
        ports are labels on the instance's own M1 pads (nothing else to draw)."""
        insts = self.netlist[subckt]
        assert [(i["master"], i["nodes"]) for i in insts] == [
            ("efuse_ls", ["row_sel", "wl", "vdd33", "vprog", "vss"])], \
            f"efuse_rowdrv netlist changed: {insts}"
        cell = self.layout.create_cell(subckt)
        cell.insert(kdb.CellInstArray(self.cells["efuse_ls"].cell_index(), kdb.Trans(0, 0)))
        lp = self.ls_ports
        for net, iname, port in (("row_sel", "XMni", "U0_G"), ("wl", "XMn2", "U0_D"),
                                 ("vdd33", "XMpi", "TAP_W"), ("vprog", "XMp1", "TAP_S"),
                                 ("vss", "XMn1", "TAP_S")):
            self._label(cell, net, lp[iname][port][0], lp[iname][port][1])
        self.cells[subckt] = cell
        return cell

    def coldrv_cell(self, subckt):
        """efuse_coldrv: one routed efuse_ls at the origin and a row of leaf
        devices east of it (Mdrv as m=3 parallel units), all 13 nets drawn.

        Every signal pin gets via1 + an M2 pad + via2 and a vertical M3 lane
        (S lane CD_SHIFT west of its pin, G on it, D CD_SHIFT east, so a
        device's three lanes are 0.59 um apart) up to its net's M2 track in a
        channel above everything; the M3 lanes only meet M2 at their own via2.
        A source whose net is its body net is merged into the guard ring with
        the ls_cell M1 bridge; each ring then leaves at TAP_S, down an M3 lane
        to that supply's M2 rail below the row. efuse_ls is entered through
        shapes it already exposes: `in` by an M3 run west off its in strip,
        `out` by an M3 run east off its out vertical, vdd33 at the west end of
        its M2 stub, vprog by extending its M2 run east, vss by extending its
        rail east.
        """
        insts = self.netlist[subckt]
        cell = self.layout.create_cell(subckt)
        ls, lp = self.cells["efuse_ls"], self.ls_ports
        cell.insert(kdb.CellInstArray(ls.cell_index(), kdb.Trans(0, 0)))
        lsr, lst = ls.bbox().right * DBU_UM, ls.bbox().top * DBU_UM
        net_pins, taps = {}, []  # net -> [(lane_x, y0, has_m2_pad)]; [(net, x, y, with_pad)]
        label_at = {}

        # -- efuse_ls attachments
        inn = insts[[i["name"] for i in insts].index("Xls")]["nodes"]
        n_in, n_out, n_vdd, n_vprog, n_vss = inn
        assert (n_vdd, n_vprog, n_vss) == SUPPLY, "efuse_ls supply nets changed"
        gni, gpi = lp["XMni"]["U0_G"], lp["XMpi"]["U0_G"]
        y_in = gpi[1] - 0.3
        x_w = -1.7
        self._box(cell, LS_M3, x_w - LS_W3N / 2, y_in - LS_W3N / 2, gni[0], y_in + LS_W3N / 2)
        net_pins.setdefault(n_in, []).append((x_w, y_in, False))  # M3-to-M3 tie-in: no M2 below
        tw = lp["XMpi"]["TAP_W"]
        taps.append((n_vdd, -0.9, tw[1], False))
        dn2, dp2 = lp["XMn2"]["U0_D"], lp["XMp2"]["U0_D"]
        mx = dp2[0] + 0.06
        x_o = gs(lsr + 1.0)
        x_v = gs(x_o + CD_LANE_PITCH)
        y_out = 14.4
        self._box(cell, LS_M3, mx - LS_W3N / 2, y_out - LS_W3N / 2, x_o + LS_W3N / 2, y_out + LS_W3N / 2)
        net_pins.setdefault(n_out, []).append((x_o, y_out, False))  # M3-to-M3 tie-in: no M2 below
        ts1, ts2 = lp["XMp1"]["TAP_S"], lp["XMp2"]["TAP_S"]
        self._box(cell, LS_M2, ts2[0], ts1[1] - LS_W2 / 2, x_v + LS_PAD2 / 2, ts1[1] + LS_W2 / 2)
        taps.append((n_vprog, x_v, ts1[1], False))

        # -- leaf devices
        units = []  # (iname, inst, child, rep, x)
        x = gs(x_v + CD_LANE_PITCH + 1.5)
        for inst in insts:
            if inst["master"] == "efuse_ls":
                continue
            child = self.leaf(subckt, inst)
            rep = self.reports[f"{subckt}__{inst['name'][1:]}"]
            for k in range(int(inst["params"].get("m", "1"))):
                units.append((inst["name"], inst, child, rep, x, k))
                x = gs(x + child.bbox().width() * DBU_UM + GAP_UM + 0.01)
        rail_x = {n: [] for n in SUPPLY}
        for iname, inst, child, rep, col, k in units:
            dx, dy = self.place(cell, child, col, 0.0)
            pt = {p["name"]: (gs(dx + p["x_um"]), gs(dy + p["y_um"]), p["width_um"])
                  for p in rep["ports"]}
            d, g, s, b = inst["nodes"]
            if s == b and b in SUPPLY:
                sp, tp = pt["U0_S"], pt["TAP_W"]
                self._box(cell, LS_M1, tp[0] - LS_W1 / 2, sp[1] - sp[2] / 2,
                          sp[0] - LS_W1 / 2, sp[1] + sp[2] / 2)
            else:
                assert s not in SUPPLY, f"{iname}: supply source off its body"
                sp = pt["U0_S"]
                self._stack(cell, sp[0], sp[1], gs(sp[0] - CD_SHIFT), via2=False)
                net_pins.setdefault(s, []).append((gs(sp[0] - CD_SHIFT), sp[1], True))
                label_at.setdefault(s, (sp[0], sp[1]))
            for net, port, sh in ((d, "U0_D", CD_SHIFT), (g, "U0_G", 0.0)):
                assert net not in SUPPLY, f"{iname}: supply on {port}"
                p = pt[port]
                self._stack(cell, p[0], p[1], gs(p[0] + sh), via2=False)
                net_pins.setdefault(net, []).append((gs(p[0] + sh), p[1], True))
                label_at.setdefault(net, (p[0], p[1]))
            tp = pt["TAP_S"]
            taps.append((b, tp[0], tp[1], True))
            label_at.setdefault(b, (tp[0], tp[1]))

        # -- tracks above, rails below
        y = gs(lst + 1.5)
        track_y = {}
        for net, pins in net_pins.items():
            if len(pins) < 2:
                continue
            track_y[net] = y
            xs = [p[0] for p in pins]
            self._box(cell, LS_M2, min(xs) - LS_W2 / 2, y - LS_W2 / 2, max(xs) + LS_W2 / 2, y + LS_W2 / 2)
            for lx, y0, pad in pins:
                # land0 only where _stack left an M2 pad for the cut to land on
                self._ls_vstrip(cell, lx, y0, y, LS_W3N, land0=pad, land1=True)
                if pad:
                    self._cut(cell, LS_VIA2, lx, y0)
                self._cut(cell, LS_VIA2, lx, y)
            y = gs(y + CD_TRACK_PITCH)
        for net, tx, ty, pad in taps:
            ry = CD_RAIL_Y[net]
            if pad:
                self._stack(cell, tx, ty)
            else:
                self._cut(cell, LS_VIA2, tx, ty)
            self._ls_vstrip(cell, tx, ty, ry, LS_W3N, land0=True, land1=True)
            self._cut(cell, LS_VIA2, tx, ry)
            rail_x[net].append(tx)
        for net, xs in rail_x.items():
            lo = min(xs + ([CD_LS_RAIL_END - 1.0] if net == "vss" else []))
            ry = CD_RAIL_Y[net]
            self._box(cell, LS_M2, lo - LS_W2 / 2, ry - LS_W2 / 2, max(xs) + LS_W2 / 2, ry + LS_W2 / 2)
        for net, (lx, ly) in label_at.items():
            self._label(cell, net, lx, ly)
        self.cd_ports = {"net_pins": net_pins, "label_at": label_at,
                         "track_y": track_y, "rail_x": rail_x}
        self.cells[subckt] = cell
        return cell

    # -- efuse_comp / efuse_sense: one row, lanes up, tracks above, rails below

    def _row_unit(self, cell, subckt, inst, x):
        """Place one row unit with its bbox lower-left at (x, 0): a leaf
        device, or an already-routed subcircuit (efuse_comp inside
        efuse_sense) kept unshifted in y so its supply rails stay at CS_RAIL_Y
        and merge with this cell's own rails. Returns the unit's port table
        (leaf reports' absolute pin positions) or None (subcircuit)."""
        if inst["kind"] == "x" and inst["master"] in self.netlist \
                and inst["master"] != "efuse":
            child = self.cells[inst["master"]]
            bb = child.bbox()
            dx = snap(round(x / DBU_UM)) - bb.left
            cell.insert(kdb.CellInstArray(child.cell_index(), kdb.Trans(dx, 0)))
            return {"iname": inst["name"], "inst": inst, "child": child,
                    "rep": None, "pt": None, "w": bb.width() * DBU_UM,
                    "top": bb.top * DBU_UM, "dx": dx * DBU_UM, "sub": inst["master"]}
        child = self.leaf(subckt, inst)
        rep = self.reports[f"{subckt}__{inst['name'][1:]}"]
        dx, dy = self.place(cell, child, x, 0.0)
        pt = {p["name"]: (gs(dx + p["x_um"]), gs(dy + p["y_um"]), p["width_um"])
              for p in rep["ports"]}
        bb = child.bbox()
        return {"iname": inst["name"], "inst": inst, "child": child, "rep": rep,
                "pt": pt, "w": bb.width() * DBU_UM, "top": bb.top * DBU_UM,
                "dx": None, "sub": None}

    def _unit_pins(self, cell, u, net_pins, taps, label_at):
        """Stacks, ring bridges and taps for one row unit (see coldrv_cell:
        same conventions -- S lane 0.16 um west of its pin, G on it, D 0.16 um
        east; a source on its body net is merged into the guard ring with an
        M1 bridge and the ring leaves at TAP_S; a resistor's two heads are
        signals with lanes on the pad centres)."""
        inst, pt = u["inst"], u["pt"]
        if inst["master"] == "ppolyf_u":
            a, b, bulk = inst["nodes"]
            assert bulk == "vss", f"{u['iname']}: resistor bulk off vss"
            for net, port in ((a, "R0_A"), (b, "R0_B")):
                p = pt[port]
                self._stack(cell, p[0], p[1], p[0], via2=False)
                net_pins.setdefault(net, []).append((p[0], p[1], True))
                label_at.setdefault(net, (p[0], p[1]))
            return
        d, g, s, b = inst["nodes"]
        if s == b and b in SUPPLY:
            sp, tp = pt["U0_S"], pt["TAP_W"]
            self._box(cell, LS_M1, tp[0] - LS_W1 / 2, sp[1] - sp[2] / 2,
                      sp[0] - LS_W1 / 2, sp[1] + sp[2] / 2)
        else:
            assert s not in SUPPLY, f"{u['iname']}: supply source off its body"
            sp = pt["U0_S"]
            self._stack(cell, sp[0], sp[1], gs(sp[0] - CD_SHIFT), via2=False)
            net_pins.setdefault(s, []).append((gs(sp[0] - CD_SHIFT), sp[1], True))
            label_at.setdefault(s, (sp[0], sp[1]))
        for net, port, sh in ((d, "U0_D", CD_SHIFT), (g, "U0_G", 0.0)):
            assert net not in SUPPLY or port == "U0_G", \
                f"{u['iname']}: supply on {port}"
            p = pt[port]
            self._stack(cell, p[0], p[1], gs(p[0] + sh), via2=False)
            net_pins.setdefault(net, []).append((gs(p[0] + sh), p[1], True))
            label_at.setdefault(net, (p[0], p[1]))
        tp = pt["TAP_S"]
        taps.append((b, tp[0], tp[1], True))
        label_at.setdefault(b, (tp[0], tp[1]))

    def _row_channels(self, cell, net_pins, taps, rail_x, y):
        """One M2 track per multi-pin net (stacked from y at CD_TRACK_PITCH),
        lanes from every pin up to its net's track, and the supply rails below
        the row with one lane down per ring tap. Returns (net -> track y)."""
        track_y = {}
        for net, pins in net_pins.items():
            if len(pins) < 2:
                continue
            track_y[net] = y
            xs = [p[0] for p in pins]
            self._box(cell, LS_M2, min(xs) - LS_W2 / 2, y - LS_W2 / 2, max(xs) + LS_W2 / 2, y + LS_W2 / 2)
            for lx, y0, pad in pins:
                self._box(cell, LS_M3, lx - LS_W3N / 2, y0 - M3_END, lx + LS_W3N / 2, y + M3_END)
                if pad:  # only where _stack left an M2 pad for the cut to land on
                    self._cut(cell, LS_VIA2, lx, y0)
                self._cut(cell, LS_VIA2, lx, y)
            y = gs(y + CD_TRACK_PITCH)
        for net, tx, ty, pad in taps:
            ry = CS_RAIL_Y[net]
            if pad:
                self._stack(cell, tx, ty)
            else:
                self._cut(cell, LS_VIA2, tx, ty)
            self._box(cell, LS_M3, tx - LS_W3N / 2, ry - M3_END, tx + LS_W3N / 2, ty + M3_END)
            self._cut(cell, LS_VIA2, tx, ry)
            rail_x.setdefault(net, []).append(tx)
        for net, xs in rail_x.items():
            ry = CS_RAIL_Y[net]
            self._box(cell, LS_M2, min(xs) - LS_W2 / 2, ry - LS_W2 / 2, max(xs) + LS_W2 / 2, ry + LS_W2 / 2)
        return track_y

    def _row_place_all(self, cell, subckt):
        """Place every instance of subckt in netlist order as one row,
        2 um between bounding boxes. Returns the units."""
        units, x = [], 0.0
        for inst in self.netlist[subckt]:
            u = self._row_unit(cell, subckt, inst, x)
            units.append(u)
            x = gs(x + u["w"] + GAP_UM + 0.01)
        return units

    def comp_cell(self, subckt):
        """efuse_comp on a one-row floorplan (netlist order west to east:
        XMt XM1 XM2 XMx1 XMx2 XMr1 XMr2), routed coldrv-style: via1 + M2 pad +
        via2 + M3 lane per signal pin, one M2 track per multi-pin net (tail,
        outp, outn, clkn) above the row, vss / vdd33 rails below it. The five
        signal-pin nets' lanes extend CS_EXPORT above the channel and their
        (x, y) tops are recorded in self.comp_export so efuse_sense can tie
        into them by overlapping M3; the rails are at CS_RAIL_Y so
        efuse_sense's own rails merge with them where they cross the instance.
        """
        expected = {"XMt", "XM1", "XM2", "XMx1", "XMx2", "XMr1", "XMr2"}
        assert {i["name"] for i in self.netlist[subckt]} == expected, \
            f"efuse_comp netlist changed: {sorted(i['name'] for i in self.netlist[subckt])}"
        cell = self.layout.create_cell(subckt)
        net_pins, taps, label_at, rail_x = {}, [], {}, {n: [] for n in CS_RAIL_Y}
        units = self._row_place_all(cell, subckt)
        for u in units:
            self._unit_pins(cell, u, net_pins, taps, label_at)
        track_y = self._row_channels(cell, net_pins, taps, rail_x,
                                     gs(max(u["top"] for u in units) + 1.5))
        # Pin exports: inp / inn are single-pin nets here (no track), so their
        # lanes and pin cuts are drawn now; clkn / outp / outn extend their
        # existing track lanes up past the channel.
        ytop = gs(max(track_y.values(), default=0.0) + CD_TRACK_PITCH + CS_EXPORT)
        export = {}
        for net, iname, port in (("inp", "XM1", "U0_G"), ("inn", "XM2", "U0_G")):
            u = next(u for u in units if u["iname"] == iname)
            lx, ypin = gs(u["pt"][port][0]), u["pt"][port][1]
            self._box(cell, LS_M3, lx - LS_W3N / 2, ypin - M3_END, lx + LS_W3N / 2, ytop + M3_END)
            self._cut(cell, LS_VIA2, lx, ypin)
            export[net] = (lx, ytop)
        for net in ("clkn", "outp", "outn"):
            lx = net_pins[net][0][0]
            self._box(cell, LS_M3, lx - LS_W3N / 2, track_y[net] - M3_END, lx + LS_W3N / 2, ytop + M3_END)
            export[net] = (lx, ytop)
        self.comp_export = export
        for net, (lx, ly) in label_at.items():
            self._label(cell, net, lx, ly)
        self.cells[subckt] = cell
        return cell

    def sense_cell(self, subckt):
        """efuse_sense on a one-row floorplan: the twenty leaf instances
        (sixteen MOS, two ppolyf_u resistors, the W=60 select folded to six
        fingers) and the routed efuse_comp instance, all in netlist order,
        routed the same coldrv way (lanes up to one M2 track per multi-pin
        net above the row, supply rails below). The comparator is entered
        through shapes it already exposes: its five exported pin lanes are
        extended (overlapping M3) up to their nets' tracks in this cell's
        channel, and its rails merge with this cell's (same y, one long box).
        """
        expected = {"XMb", "XRb", "XMbs", "XMbp", "XMf", "XMrf", "XRref", "XMsw",
                    "XMsel", "XMpca", "XMpcb", "XMnca", "XMncb", "Xcmp",
                    "XMpqa", "XMpqb", "XMnqa", "XMnqb", "XMpba", "XMpbb",
                    "XMnba", "XMnbb"}
        assert {i["name"] for i in self.netlist[subckt]} == expected, \
            f"efuse_sense netlist changed: {sorted(i['name'] for i in self.netlist[subckt])}"
        cell = self.layout.create_cell(subckt)
        net_pins, taps, label_at, rail_x = {}, [], {}, {n: [] for n in CS_RAIL_Y}
        units = self._row_place_all(cell, subckt)
        cmpu = next(u for u in units if u["sub"] == "efuse_comp")
        # The comparator's rail span joins this cell's rails (same y), so they
        # merge where they cross the instance; its five exported pin lanes
        # become pin entries of their nets (no M2 pad at the tie-in point: the
        # lane is efuse_comp's own M3, extended up by the channel tracks).
        for net in CS_RAIL_Y:
            rail_x[net] += [cmpu["dx"] + 0.5, cmpu["dx"] + cmpu["w"] - 0.5]
        for u in units:
            if u["sub"] is None:
                self._unit_pins(cell, u, net_pins, taps, label_at)
        nodes = cmpu["inst"]["nodes"]  # inp inn clkn outp outn vdd33 vss
        for net, pin in zip(nodes[:5], ("inp", "inn", "clkn", "outp", "outn")):
            lx, ytop = self.comp_export[pin]
            net_pins.setdefault(net, []).append((gs(cmpu["dx"] + lx), ytop, False))
        track_y = self._row_channels(cell, net_pins, taps, rail_x,
                                     gs(max(u["top"] for u in units) + 1.5))
        for net, (lx, ly) in label_at.items():
            self._label(cell, net, lx, ly)
        self.sa_ports = {"net_pins": net_pins, "label_at": label_at,
                         "track_y": track_y, "rail_x": rail_x}
        self.cells[subckt] = cell
        return cell

    # -- efuse_otp_array: top-level array, driver, sense and supply routing --

    def _via_grid(self, cell, layer, xs, ys):
        for x in xs:
            for y in ys:
                self._cut(cell, layer, x, y)

    @staticmethod
    def _via_span(x0, n):
        return [gs(x0 + i * TOP_VIA_PITCH) for i in range(n)]

    def _via_center_span(self, xc, n):
        return self._via_span(xc - (n - 1) * TOP_VIA_PITCH / 2, n)

    def _m2_to_m5_strip(self, cell, xs, y):
        """Horizontal row of stacked via2 + M3 pad + via3 + M4 pad + via4 on an
        existing M2 rail at y, landing into an overlying M5 trunk."""
        self._via_grid(cell, LS_VIA2, xs, [y])
        self._box(cell, LS_M3, xs[0] - LS_W3 / 2, y - LS_W3 / 2,
                  xs[-1] + LS_W3 / 2, y + LS_W3 / 2)
        self._via_grid(cell, TOP_VIA3, xs, [y])
        self._box(cell, TOP_M4, xs[0] - LS_W3 / 2, y - LS_W3 / 2,
                  xs[-1] + LS_W3 / 2, y + LS_W3 / 2)
        self._via_grid(cell, TOP_VIA4, xs, [y])

    def route_array_top(self, cell, row_xy, rd_xy, cd_xy, sa_xy, step_x, step_y):
        """Wire the 32 rows, 32 row drivers, 8 column drivers and sense block.

        Planes (no constituent cell is modified; every subcell uses M1-M3):
          * M2: 32 short L-shaped wl[r] bridges across the rowdrv-to-row gap.
          * M3: local landing pads on subcell M2 rails/pads (all in M3-free
            windows) transitioning via2 -> via3.
          * M4: horizontal shared buses (prog_strobe, sense_en, sbl), per-column
            local jumpers (bl, vprog over efuse_coldrv), vertical supply rails
            over efuse_rowdrv (y >= -4), and the three south horizontal main
            supply buses (vss 12 um, vprog 12 um, vdd33 4 um).
          * M5 (MetalTop on 5LM gf180mcuC): vertical per-column trunks (6 um
            bl[c] and vss, 6 um vprog feeder, 1.2 um vdd33 feeder), west
            row-driver supply drops, and 0.8 um sense_en / sbl drops to
            efuse_sense.
        Column k (0..7 west to east) carries index c = COLS - 1 - k (7..0),
        matching efuse_row's pin order and Xcd[c] / Xarr[r] in the netlist.
        """
        for pair in (TOP_VIA3, TOP_M4, TOP_VIA4, TOP_M5):
            self.layout.layer(*pair)

        dx_row, dy_row = row_xy
        dx_rd, dy_rd = rd_xy
        dx_cd, dy_cd = cd_xy
        dx_sa, dy_sa = sa_xy
        lp, bp = self.ls_ports, self.bc_ports
        cd_pins, cd_lbl, cd_ty, cd_rx = (
            self.cd_ports["net_pins"], self.cd_ports["label_at"],
            self.cd_ports["track_y"], self.cd_ports["rail_x"])
        sa_pins, sa_lbl = self.sa_ports["net_pins"], self.sa_ports["label_at"]

        # 1. Word lines wl[0..31] (M2 L-bridges in the rowdrv-to-row gap) and
        #    row_sel[0..31] top-level M1 pin labels.
        x_jog = -1.00
        rd_wl_x = gs(dx_rd + lp["XMn2"]["U0_D"][0])
        for r in range(ROWS):
            y_rd_wl = gs(dy_rd + r * step_y + lp["XMn2"]["U0_D"][1])
            y_row_wl = gs(dy_row + r * step_y + sum(ROW_WL_RAIL_Y) / 2)
            self._box(cell, LS_M2, rd_wl_x, y_rd_wl - LS_W2 / 2,
                      x_jog + LS_W2 / 2, y_rd_wl + LS_W2 / 2)
            self._box(cell, LS_M2, x_jog - LS_W2 / 2,
                      min(y_row_wl, y_rd_wl) - LS_W2 / 2,
                      x_jog + LS_W2 / 2, max(y_row_wl, y_rd_wl) + LS_W2 / 2)
            self._box(cell, LS_M2, x_jog - LS_W2 / 2, y_row_wl - LS_W2 / 2,
                      dx_row + 0.50, y_row_wl + LS_W2 / 2)
            self._label(cell, f"wl[{r}]", gs(dx_row + bp["wl"][0]),
                        gs(dy_row + r * step_y + bp["wl"][1]))
            self._label(cell, f"row_sel[{r}]", gs(dx_rd + lp["XMni"]["U0_G"][0]),
                        gs(dy_rd + r * step_y + lp["XMni"]["U0_G"][1]))

        # 2. Row-driver vertical supply rails (M4 over the 32 row drivers,
        #    transitioning to M5 at y=-4..-2 down to the south M4 supply buses).
        rd_rails = (
            ("vdd33", -0.80, lp["XMpi"]["TAP_W"][1]),
            ("vss", 4.00, LS_VSS_RAIL_Y),
            ("vprog", 9.50, lp["XMp1"]["TAP_S"][1]),
        )
        rd_rail_x = {}
        for net, x_loc, y_loc in rd_rails:
            xc = gs(dx_rd + x_loc)
            rd_rail_x[net] = xc
            for r in range(ROWS):
                yc = gs(dy_rd + r * step_y + y_loc)
                self._cut(cell, LS_VIA2, xc, yc)
                self._box(cell, LS_M3, xc - LS_W3 / 2, yc - LS_W3 / 2,
                          xc + LS_W3 / 2, yc + LS_W3 / 2)
                self._cut(cell, TOP_VIA3, xc, yc)
            y_top = gs(dy_rd + (ROWS - 1) * step_y + y_loc + LS_W3 / 2)
            self._box(cell, TOP_M4, xc - TOP_RD_RAIL_W / 2, -4.00,
                      xc + TOP_RD_RAIL_W / 2, y_top)
            vxs = self._via_center_span(xc, 2)
            self._via_grid(cell, TOP_VIA4, vxs, self._via_center_span(-3.00, 3))
            by0, by1 = TOP_BUS_Y[net]
            self._box(cell, TOP_M5, xc - TOP_RD_RAIL_W / 2, by0,
                      xc + TOP_RD_RAIL_W / 2, -2.00)
            self._via_grid(cell, TOP_VIA4, vxs,
                           self._via_center_span((by0 + by1) / 2, 3))

        # 3. Per-column bit lines bl[7..0] (6 um M5 vertical trunks + 4 um M4
        #    jumpers over efuse_coldrv) and col_sel[7..0] labels.
        y_bl_track = gs(dy_cd + cd_ty["bl"])
        y_bl_bar0 = gs(y_bl_track - TOP_BL_BAR_W / 2)
        y_bl_bar1 = gs(y_bl_track + TOP_BL_BAR_W / 2)
        y_bl_top = gs(dy_row + (ROWS - 1) * step_y + BC_PAD_Y + 0.21)
        mdrv_dx = [p[0] for p in cd_pins["bl"][:3]]
        assert len(mdrv_dx) == 3, f"expected 3 Mdrv drain lanes, got {mdrv_dx}"
        bl_cut_x = [gs(x) for x in BC_BL_CUT_X]  # 0.93, 1.48 in bitcell coords
        for k in range(COLS):
            c = COLS - 1 - k
            x_col = gs(dx_row + k * step_x)
            x_cd = gs(dx_cd + k * step_x)
            # 6 um vertical M5 trunk covering all 32 rows' bl M3 lanes
            self._box(cell, TOP_M5, x_col, y_bl_bar0,
                      x_col + TOP_TRUNK_W, y_bl_top)
            for r in range(ROWS):
                ys = [gs(dy_row + r * step_y + BC_BL_LANE_Y0 + 0.60 + j * TOP_VIA_PITCH)
                      for j in range(4)]
                xs = [gs(x_col + x) for x in bl_cut_x]
                self._via_grid(cell, TOP_VIA3, xs, ys)
                self._box(cell, TOP_M4, xs[0] - 0.21, ys[0] - 0.21,
                          xs[-1] + 0.21, ys[-1] + 0.21)
                self._via_grid(cell, TOP_VIA4, xs, ys)
            # Tap efuse_coldrv[k]'s bl M2 track beside all three Mdrv drains
            for mx in mdrv_dx:
                cxs = self._via_span(x_cd + mx + 1.20, 4)
                self._via_grid(cell, LS_VIA2, cxs, [y_bl_track])
                self._box(cell, LS_M3, cxs[0] - LS_W3 / 2, y_bl_track - LS_W3 / 2,
                          cxs[-1] + LS_W3 / 2, y_bl_track + LS_W3 / 2)
                self._via_grid(cell, TOP_VIA3, cxs, [y_bl_track])
            x_bar1 = gs(x_cd + mdrv_dx[-1] + 1.20 + 3 * TOP_VIA_PITCH + LS_W3 / 2 + 0.20)
            self._box(cell, TOP_M4, x_col, y_bl_bar0, x_bar1, y_bl_bar1)
            self._via_grid(cell, TOP_VIA4, self._via_span(x_col + 1.50, 5),
                           self._via_center_span(y_bl_track, 3))
            self._label(cell, f"bl[{c}]", gs(x_cd + cd_lbl["bl"][0]),
                        gs(dy_cd + cd_lbl["bl"][1]))
            self._label(cell, f"col_sel[{c}]", gs(x_cd + cd_lbl["col_sel"][0]),
                        gs(dy_cd + cd_lbl["col_sel"][1]))

        # 4. Shared control & sense buses: prog_strobe, sense_en, sbl (M4
        #    horizontal across all 8 column drivers; M5 drops to efuse_sense).
        ps_x = cd_pins["prog_strobe"][0][0]
        y_ps = TOP_SIG_Y["prog_strobe"]
        self._box(cell, TOP_M4, gs(dx_cd + ps_x - TOP_M4_SIG_W / 2),
                  y_ps - TOP_M4_SIG_W / 2,
                  gs(dx_cd + (COLS - 1) * step_x + ps_x + TOP_M4_SIG_W / 2),
                  y_ps + TOP_M4_SIG_W / 2)
        for k in range(COLS):
            self._cut(cell, TOP_VIA3, gs(dx_cd + k * step_x + ps_x), y_ps)

        se_cd_x = cd_pins["sense_en"][0][0]
        sa_se_x = gs(dx_sa + sa_pins["sense_en"][0][0])
        y_se = TOP_SIG_Y["sense_en"]
        self._box(cell, TOP_M4, sa_se_x - TOP_M4_SIG_W / 2, y_se - TOP_M4_SIG_W / 2,
                  gs(dx_cd + (COLS - 1) * step_x + se_cd_x + TOP_M4_SIG_W / 2),
                  y_se + TOP_M4_SIG_W / 2)
        for k in range(COLS):
            self._cut(cell, TOP_VIA3, gs(dx_cd + k * step_x + se_cd_x), y_se)
        y_sa_se = TOP_SA_TAP_Y["sense_en"]
        self._cut(cell, TOP_VIA3, sa_se_x, y_sa_se)
        self._box(cell, TOP_M4, sa_se_x - TOP_M4_SIG_W / 2, y_sa_se - TOP_M4_SIG_W / 2,
                  sa_se_x + TOP_M4_SIG_W / 2, y_sa_se + TOP_M4_SIG_W / 2)
        self._cut(cell, TOP_VIA4, sa_se_x, y_sa_se)
        self._cut(cell, TOP_VIA4, sa_se_x, y_se)
        self._box(cell, TOP_M5, sa_se_x - TOP_M5_SIG_W / 2, y_sa_se - TOP_M5_SIG_W / 2,
                  sa_se_x + TOP_M5_SIG_W / 2, y_se + TOP_M5_SIG_W / 2)

        sbl_cd_x = gs(cd_pins["sbl"][0][0] + 0.08)  # centre of Mrs.S M2 pad
        y_sbl = gs(dy_cd + cd_pins["sbl"][0][1])
        sa_sbl_x = gs(dx_sa + sa_pins["sbl"][-1][0])  # comparator-side M3 lane
        self._box(cell, TOP_M4, sa_sbl_x - TOP_M4_SIG_W / 2, y_sbl - TOP_M4_SIG_W / 2,
                  gs(dx_cd + (COLS - 1) * step_x + sbl_cd_x + TOP_M4_SIG_W / 2),
                  y_sbl + TOP_M4_SIG_W / 2)
        for k in range(COLS):
            xc = gs(dx_cd + k * step_x + sbl_cd_x)
            self._cut(cell, LS_VIA2, xc, y_sbl)
            self._box(cell, LS_M3, xc - LS_W3 / 2, y_sbl - LS_W3 / 2,
                      xc + LS_W3 / 2, y_sbl + LS_W3 / 2)
            self._cut(cell, TOP_VIA3, xc, y_sbl)
        y_sa_sbl = TOP_SA_TAP_Y["sbl"]
        self._cut(cell, TOP_VIA3, sa_sbl_x, y_sa_sbl)
        self._box(cell, TOP_M4, sa_sbl_x - TOP_M4_SIG_W / 2, y_sa_sbl - TOP_M4_SIG_W / 2,
                  sa_sbl_x + TOP_M4_SIG_W / 2, y_sa_sbl + TOP_M4_SIG_W / 2)
        self._cut(cell, TOP_VIA4, sa_sbl_x, y_sa_sbl)
        self._cut(cell, TOP_VIA4, sa_sbl_x, y_sbl)
        self._box(cell, TOP_M5, sa_sbl_x - TOP_M5_SIG_W / 2, y_sa_sbl - TOP_M5_SIG_W / 2,
                  sa_sbl_x + TOP_M5_SIG_W / 2, y_sbl + TOP_M5_SIG_W / 2)

        # 5. Per-column supply trunks (M5) and south horizontal main buses (M4):
        #    vss (6 um M5 per column beside every bitcell's vss exit, 12 um M4 bus),
        #    vprog (6 um M5 per column into all 3 Mdrv taps, 12 um M4 bus),
        #    vdd33 (1.2 um M5 per column, 4 um M4 bus).
        y_vss_top = gs(dy_row + (ROWS - 1) * step_y + ROW_VSS_RAIL_Y[1] + 0.30)
        y_cd_vss = gs(dy_cd + CD_RAIL_Y["vss"])
        y_cd_vdd = gs(dy_cd + CD_RAIL_Y["vdd33"])
        y_cd_vp = gs(dy_cd + CD_RAIL_Y["vprog"])
        mdrv_vp_x = cd_rx["vprog"][1:]
        assert len(mdrv_vp_x) == 3, f"expected 3 Mdrv vprog taps, got {mdrv_vp_x}"
        vss_by0, vss_by1 = TOP_BUS_Y["vss"]
        vp_by0, vp_by1 = TOP_BUS_Y["vprog"]
        vdd_by0, vdd_by1 = TOP_BUS_Y["vdd33"]
        for k in range(COLS):
            x_col = gs(dx_row + k * step_x)
            x_cd = gs(dx_cd + k * step_x)

            # vss trunk
            vx0, vx1 = gs(x_col + TOP_VSS_COL_X[0]), gs(x_col + TOP_VSS_COL_X[1])
            self._box(cell, TOP_M5, vx0, vss_by0, vx1, y_vss_top)
            row_vss_xs = self._via_span(x_col + 24.50, 8)
            row_east = gs(dx_row + self.size(self.cells["efuse_row"])[0])
            for r in range(ROWS):
                y_r_vss = gs(dy_row + r * step_y + sum(ROW_VSS_RAIL_Y) / 2)
                if k == COLS - 1:
                    # efuse_row's vss rail ends at bitcell 7's east edge (973.815);
                    # extend it east on M2 under column 7's vss trunk so all 8 via2s land.
                    self._box(cell, LS_M2, row_east - 0.50,
                              gs(dy_row + r * step_y + ROW_VSS_RAIL_Y[0]),
                              vx1, gs(dy_row + r * step_y + ROW_VSS_RAIL_Y[1]))
                self._m2_to_m5_strip(cell, row_vss_xs, y_r_vss)
            self._m2_to_m5_strip(cell, self._via_span(x_cd + 24.00, 6), y_cd_vss)
            self._via_grid(cell, TOP_VIA4,
                           self._via_center_span((vx0 + vx1) / 2, 6),
                           self._via_center_span((vss_by0 + vss_by1) / 2, 6))

            # vprog feeder
            px0, px1 = gs(x_col + TOP_VPROG_COL_X[0]), gs(x_col + TOP_VPROG_COL_X[1])
            self._box(cell, TOP_M5, px0, vp_by0, px1, y_cd_vp + TOP_VPROG_BAR_W / 2)
            for start_x in (mdrv_vp_x[0] + 1.20, mdrv_vp_x[1] - 5.00,
                            mdrv_vp_x[1] + 1.20, mdrv_vp_x[2] - 4.40):
                cxs = self._via_span(x_cd + start_x, 6)
                self._via_grid(cell, LS_VIA2, cxs, [y_cd_vp])
                self._box(cell, LS_M3, cxs[0] - LS_W3 / 2, y_cd_vp - LS_W3 / 2,
                          cxs[-1] + LS_W3 / 2, y_cd_vp + LS_W3 / 2)
                self._via_grid(cell, TOP_VIA3, cxs, [y_cd_vp])
            self._box(cell, TOP_M4, gs(x_cd + mdrv_vp_x[0] + 0.99),
                      y_cd_vp - TOP_VPROG_BAR_W / 2,
                      gs(x_cd + mdrv_vp_x[2] - 0.99),
                      y_cd_vp + TOP_VPROG_BAR_W / 2)
            self._via_grid(cell, TOP_VIA4,
                           self._via_center_span((px0 + px1) / 2, 10),
                           self._via_center_span(y_cd_vp, 2))
            self._via_grid(cell, TOP_VIA4,
                           self._via_center_span((px0 + px1) / 2, 6),
                           self._via_center_span((vp_by0 + vp_by1) / 2, 6))

            # vdd33 feeder
            dx_c = gs(x_col + TOP_VDD_COL_X)
            self._box(cell, TOP_M5, dx_c - TOP_VDD_FEED_W / 2, vdd_by0,
                      dx_c + TOP_VDD_FEED_W / 2, y_cd_vdd + 0.42)
            vdd_xs = self._via_center_span(dx_c, 2)
            self._m2_to_m5_strip(cell, vdd_xs, y_cd_vdd)
            self._via_grid(cell, TOP_VIA4, vdd_xs,
                           self._via_center_span((vdd_by0 + vdd_by1) / 2, 2))

            # efuse_sense supply taps (column 0 passes directly over efuse_sense)
            if k == 0:
                y_sa_vss = gs(dy_sa + CS_RAIL_Y["vss"])
                self._m2_to_m5_strip(cell, self._via_span(dx_sa + 25.00, 4), y_sa_vss)
                y_sa_vdd = gs(dy_sa + CS_RAIL_Y["vdd33"])
                self._m2_to_m5_strip(cell, vdd_xs, y_sa_vdd)
                sa_vp_x = gs(dx_sa + sa_pins["vprog"][0][0])
                sa_vp_y = gs(dy_sa + sa_pins["vprog"][0][1])
                self._cut(cell, LS_VIA2, sa_vp_x, sa_vp_y)
                self._box(cell, LS_M3, sa_vp_x - LS_W3 / 2, sa_vp_y - LS_W3 / 2,
                          sa_vp_x + LS_W3 / 2, sa_vp_y + LS_W3 / 2)
                self._cut(cell, TOP_VIA3, sa_vp_x, sa_vp_y)
                self._box(cell, TOP_M4, sa_vp_x - TOP_M4_SIG_W / 2,
                          sa_vp_y - TOP_M4_SIG_W / 2,
                          px1, sa_vp_y + TOP_M4_SIG_W / 2)
                self._via_grid(cell, TOP_VIA4,
                               self._via_center_span((px0 + px1) / 2, 2), [sa_vp_y])

        # Three south horizontal main M4 supply buses tying all columns & west rails
        self._box(cell, TOP_M4, rd_rail_x["vss"] - TOP_RD_RAIL_W / 2, vss_by0,
                  gs(dx_row + (COLS - 1) * step_x + TOP_VSS_COL_X[1]), vss_by1)
        self._box(cell, TOP_M4, rd_rail_x["vprog"] - TOP_RD_RAIL_W / 2, vp_by0,
                  gs(dx_row + (COLS - 1) * step_x + TOP_VPROG_COL_X[1]), vp_by1)
        self._box(cell, TOP_M4, rd_rail_x["vdd33"] - TOP_RD_RAIL_W / 2, vdd_by0,
                  gs(dx_row + (COLS - 1) * step_x + TOP_VDD_COL_X + TOP_VDD_FEED_W / 2),
                  vdd_by1)

        # 6. Top-level port labels on M1 label layer (34/10).
        self._label(cell, "prog_strobe", gs(dx_cd + cd_lbl["prog_strobe"][0]),
                    gs(dy_cd + cd_lbl["prog_strobe"][1]))
        for net in ("sense_en", "clk", "sense_out", "sbl", "vdd33", "vprog", "vss"):
            self._label(cell, net, gs(dx_sa + sa_lbl[net][0]),
                        gs(dy_sa + sa_lbl[net][1]))


def masters(netlist, subckt):
    out = {}
    for inst in netlist[subckt]:
        if inst["kind"] == "x":
            out[inst["master"]] = out.get(inst["master"], 0) + 1
    return out


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
    # efuse_ls are routed (bitcell_cell, ls_cell), efuse_rowdrv / efuse_coldrv
    # are routed from it and leaf devices (rowdrv_cell, coldrv_cell), efuse_comp
    # and efuse_sense the same way (comp_cell, sense_cell).
    for name in ("efuse_bitcell", "efuse_ls", "efuse_rowdrv", "efuse_coldrv",
                 "efuse_comp", "efuse_sense"):
        if name == "efuse_bitcell":
            b.bitcell_cell(name)
        elif name == "efuse_ls":
            b.ls_cell(name)
        elif name == "efuse_rowdrv":
            b.rowdrv_cell(name)
        elif name == "efuse_coldrv":
            b.coldrv_cell(name)
        elif name == "efuse_comp":
            b.comp_cell(name)
        elif name == "efuse_sense":
            b.sense_cell(name)
        else:
            b.row_cell(name)

    bit_w, _ = b.size(b.cells["efuse_bitcell"])
    rd_w, rd_h = b.size(b.cells["efuse_rowdrv"])
    cd_w, cd_h = b.size(b.cells["efuse_coldrv"])
    sa_w, sa_h = b.size(b.cells["efuse_sense"])
    pitch_x = max(bit_w, cd_w) + GAP_UM  # bit lines line up with the column drivers
    row = b.array_row_cell(pitch_x)  # 8 routed bitcells at the column pitch
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
    b.route_array_top(t, row_xy, rd_xy, cd_xy, sa_xy, step_x, step_y)

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
            "simulated": "sim/corner-verification record 20261108T235928Z-f6eeac7: "
                         "schematic-level, all 135 points pass; binding corner ss / "
                         "125 C / vdd33 2.97 V / vprog 4.5 V / 260 ohm at 10.97 mA "
                         "(its 20 ohm route is an assumption, not this layout)",
            "current_limits": "none documented: the pinned PDK tree carries no metal "
                              "or via current limit (searched the klt deck, the PDK "
                              "DRC/LVS rule decks, libs.tech and libs.ref); the "
                              "geometry below is recorded against the 10 mA target "
                              "and PDK Magic-tech sheet/via resistances (M1-M4 0.09/0.104 "
                              "ohm/sq, M5 9K 0.04/0.049 ohm/sq, via1-via4 4.5/15.0 ohm "
                              "nom/high), not rated against a foundry current limit",
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
            "finding": "limiting segments are the constituent cells' via stacks "
                       "(efuse_bitcell: via1 x2 + via2 x2 at bl entry, via1 x2 at fuse "
                       "out, via1 x2 at vss exit = ~10.5 ohm nom / 35.0 ohm high; "
                       "efuse_coldrv: 3 parallel single-cut stacks on vprog and bl = "
                       "~9.0 ohm nom / 30.0 ohm high) and narrow M2/M3 straps, totaling "
                       "~23.6 ohm nom / ~69.6 ohm high inside the constituent cells alone "
                       "plus ~14.7 ohm nom / ~18.4 ohm high in worst-case top-level M4/M5 "
                       "trunks (Row 31, Col 7) -- exceeding the 20 ohm schematic assumption "
                       "(10.97 mA at worst corner). No foundry current rule exists to rate "
                       "the cuts; tracked as design issue #407 (ratified >= 10 mA target "
                       "kept unchanged).",
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
