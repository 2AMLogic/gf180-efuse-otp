#!/usr/bin/env python3
"""Shared core of the analog generator: parser, klt wrapper and Builder.

gen_efuse_otp.py (the CLI, build and report) and the per-cell router modules
route_ls.py, route_drivers.py, route_sense.py and route_array.py all build on
this module: the SPICE netlist parser, the pinned-klt leaf-device generator
wrapper (Klt), the grid and shared routing-layer constants, and Builder --
leaf generation and implant growth, the placement contract (footprint, place,
size) and the box/cut/label/stack drawing primitives shared by every router.

Run through layout/regen-gds.sh, which supplies the pinned klt and PDK: the
interpreter must be the pinned klt's own (it provides klayout.db) and the
leaf devices are produced by that same klt (`klt gen`).
"""

import json
import math
import re
import shlex
import subprocess
from pathlib import Path

import klayout.db as kdb

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

# gf180mcu GDS layer/datatype pairs (PDK tech layer table) shared by every
# routed cell, with the routing widths the per-cell routers draw on them (see
# route_ls.py and layout/README.md, "efuse_ls routing").
LS_M1, LS_M1_LBL = (34, 0), (34, 10)
LS_M2, LS_M3 = (36, 0), (42, 0)
LS_VIA1, LS_VIA2 = (35, 0), (38, 0)
LS_VIA_SIZE = 0.26  # the deck's fixed via1/via2 square (gf180mcu 7.14)
LS_PAD2 = 0.4  # M2 landing pad at every M1 connection point
LS_W1 = 0.42  # M1 routing width (pad width)
LS_W2 = 0.42  # M2 routing width (rails and strips)
LS_W3 = 0.42  # M3 routing width
LS_W3N = 0.30  # M3 width where two verticals share a device column


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


def masters(netlist, subckt):
    out = {}
    for inst in netlist[subckt]:
        if inst["kind"] == "x":
            out[inst["master"]] = out.get(inst["master"], 0) + 1
    return out


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

    # -- boxes, cuts and labels shared by every routed cell ---------------

    def _box(self, cell, pair, x0, y0, x1, y1):
        li = self.layout.layer(*pair)
        cell.shapes(li).insert(kdb.Box(round(gs(x0) / DBU_UM), round(gs(y0) / DBU_UM),
                                       round(gs(x1) / DBU_UM), round(gs(y1) / DBU_UM)))

    def add_program_diffusion_contacts(self, leaf, ports):
        """Distribute contacts along the 10 µm fingers of a selected program MOS."""
        m1 = kdb.Region(leaf.begin_shapes_rec(self.layout.layer(*LS_M1))).merged()
        contact_layer = self.layout.layer(33, 0)
        contacts = kdb.Region(leaf.begin_shapes_rec(contact_layer)).merged()
        for port in ports:
            if port["name"] not in ("U0_S", "U0_D"):
                continue
            point = kdb.Point(round(port["x_um"] / DBU_UM), round(port["y_um"] / DBU_UM))
            strap, = [polygon for polygon in m1.each() if polygon.inside(point)]
            fingers = contacts.inside(kdb.Region(strap))
            assert fingers.count(), f"{leaf.name}: no contacts on {port['name']} strap"
            for finger in fingers.each():
                assert finger.is_box(), f"{leaf.name}: nonrectangular diffusion contact"
                for step in (*range(-7, 0), *range(1, 8)):
                    cut = finger.bbox().moved(0, round(step * 0.60 / DBU_UM))
                    assert (kdb.Region(cut) - kdb.Region(strap)).is_empty(), \
                        f"{leaf.name}: additional contact falls outside the M1 finger"
                    leaf.shapes(contact_layer).insert(cut)

    def _cut(self, cell, pair, cx, cy):
        h = LS_VIA_SIZE / 2
        self._box(cell, pair, cx - h, cy - h, cx + h, cy + h)

    def _label(self, cell, net, x, y):
        cell.shapes(self.layout.layer(*LS_M1_LBL)).insert(
            kdb.Text(net, kdb.Trans(round(x / DBU_UM), round(y / DBU_UM))))

    def _m1_ring_bridge(self, cell, source, tap_w):
        """M1 bridge merging a source pad into its own guard ring through the
        ring's west strap (source and body are one net), as ls_cell,
        coldrv_cell and _unit_pins draw it: LS_W1 wide, from half a pad width
        west of the TAP_W strap to the source pad's west edge, at the source
        pad's own height."""
        self._box(cell, LS_M1, tap_w[0] - LS_W1 / 2, source[1] - source[2] / 2,
                  source[0] - LS_W1 / 2, source[1] + source[2] / 2)

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
