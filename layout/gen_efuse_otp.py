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

What it does not do: draw inter-device or inter-block routing, or check
anything. Connectivity is not claimed; DRC, EF.* coverage and LVS are separate
items (see layout/README.md).
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

DBU_UM = 0.0005  # the dbu `klt gen` writes for gf180mcu
GRID_DBU = 10  # the 0.005 um rule grid in database units (DBU_UM = 0.0005)
GAP_UM = 2.0  # clearance between placed cells (bboxes include guard rings)
MAX_FINGER_W_UM = 10.0  # folded devices: fingers of at most this width
# Assumption, not a design fact: the schematic carries ideal resistors, so the
# layout body is a ppolyf_u strip at this width and the model library's sheet
# resistance (sm141064.ngspice `.param rsh_ppolyf_u`).
RES_WIDTH_UM = 1.0
RSH_PPOLYF_U = 350.0

MOS_MODELS = {
    "nfet_03v3": ("nfet", ""),
    "pfet_03v3": ("pfet", ""),
    "nfet_06v0": ("nfet", "medium_voltage"),
    "pfet_06v0": ("pfet", "medium_voltage"),
}
SUFFIX = {"f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6}

# Expected shape of the array top, asserted against the netlist.
ROWS, COLS = 32, 8


def parse_value(text):
    m = re.fullmatch(r"([0-9.]+)(meg|[fpnumk])?", text.strip().lower())
    if not m:
        raise ValueError(f"cannot parse value {text!r}")
    return float(m.group(1)) * SUFFIX.get(m.group(2), 1.0)


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
        current.append({"kind": "x", "name": name, "master": plain[-1], "params": params})
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
        self.cache[key] = (str(out), report["cell_name"])
        return self.cache[key]


def snap(dbu, up=True):
    """Round a database-unit length to the rule grid, up or down."""
    q = -(-dbu // GRID_DBU) if up else dbu // GRID_DBU
    return q * GRID_DBU


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
        self.devices = []  # report rows

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
            # Length snapped to the 0.005 um rule grid (an off-grid length puts
            # the strip's vertices off it); the drawn ohms follow from it.
            step = GRID_DBU * DBU_UM
            length = round(round(inst["ohms"] / RSH_PPOLYF_U * RES_WIDTH_UM / step) * step, 3)
            gds, top = self.klt.gen("res_array", {
                "length_um": length, "width_um": RES_WIDTH_UM, "num": 1,
                "dummy": 0, "flavor": "generic"})
            self.devices.append({"cell": name, "device": "ppolyf_u", "ohms": inst["ohms"],
                                 "ohms_drawn": round(length / RES_WIDTH_UM * RSH_PPOLYF_U, 2),
                                 "length_um": length, "width_um": RES_WIDTH_UM})
            return self.import_cell(gds, top, name)
        master = inst["master"]
        if master == "efuse":
            # The PDK primitive, copied as-is (only its dbu is rescaled by an
            # exact integer); not routed through any generator.
            self.devices.append({"cell": name, "device": "efuse", "source": "PDK efuse.gds"})
            return self.import_cell(self.fuse_gds, "efuse_cell", name)
        flavor, vflavor = MOS_MODELS[master]
        w = round(parse_value(inst["params"]["W"]) * 1e6, 6)
        l = round(parse_value(inst["params"]["L"]) * 1e6, 6)
        fingers, wf = fold(w)
        gds, top = self.klt.gen("mos_array", {
            "w_um": wf, "l_um": l, "fingers": fingers, "rows": 1, "cols": 1,
            "dummy": 0, "topology": "array", "flavor": flavor,
            "voltage_flavor": vflavor, "gate_contact": True, "add_guard_ring": True})
        self.devices.append({"cell": name, "device": master, "w_um": w, "l_um": l,
                             "fingers": fingers, "finger_w_um": wf})
        return self.import_cell(gds, top, name)

    def bbox(self, cell):
        return cell.bbox()

    def place(self, parent, child, x_um, y_um, rows=1, cols=1, pitch_x_um=0.0, pitch_y_um=0.0,
              away_x=True, away_y=True):
        """Instance of child with its bbox lower-left at (x_um, y_um), snapped.

        The child's bbox edges are vertices (guard rings; the PDK fuse stream's
        own origin is off the grid by one stream dbu), so landing the lower-left
        on the rule grid puts every vertex on it. The lower-left is rounded away
        from the placed neighbours (up, or down with away_* False) so the
        clearance is never reduced; the pitches are rounded up to the grid.
        """
        bb = child.bbox()
        dx = snap(round(x_um / DBU_UM), away_x) - bb.left
        dy = snap(round(y_um / DBU_UM), away_y) - bb.bottom
        trans = kdb.Trans(dx, dy)
        if rows == 1 and cols == 1:
            parent.insert(kdb.CellInstArray(child.cell_index(), trans))
        else:
            parent.insert(kdb.CellInstArray(
                child.cell_index(), trans,
                kdb.Vector(snap(round(pitch_x_um / DBU_UM)), 0),
                kdb.Vector(0, snap(round(pitch_y_um / DBU_UM))), cols, rows))

    def size(self, cell):
        bb = cell.bbox()
        return bb.width() * DBU_UM, bb.height() * DBU_UM

    def row_cell(self, subckt):
        """A subcircuit as one left-to-right row of its leaf and sub-cells."""
        cell = self.layout.create_cell(subckt)
        x = 0.0
        for inst in self.netlist[subckt]:
            child = (self.cells[inst["master"]] if inst["kind"] == "x" and inst["master"] in self.netlist
                     else self.leaf(subckt, inst))
            self.place(cell, child, x, 0.0)
            x += self.size(child)[0] + GAP_UM + GRID_DBU * DBU_UM  # snap slack
        self.cells[subckt] = cell
        return cell


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
        ref_layers.add((info.layer, info.datatype))
        mi = layout.find_layer(info.layer, info.datatype)
        mine = kdb.Region(cell.begin_shapes_rec(mi)) if mi is not None else kdb.Region()
        theirs = kdb.Region(ref_top.begin_shapes_rec(li)).transformed(kdb.ICplxTrans(scale))
        if (mine ^ theirs).count():
            print(f"fuse differs from the PDK primitive on layer {info.layer}/{info.datatype}",
                  file=sys.stderr)
            sys.exit(4)
    mine_layers = {(layout.get_info(i).layer, layout.get_info(i).datatype)
                   for i in layout.layer_indexes() if not cell.bbox_per_layer(i).empty()}
    if mine_layers != ref_layers:
        print("fuse layer set differs from the PDK primitive", file=sys.stderr)
        sys.exit(4)


def build(netlist_path, klt, fuse_gds, out_gds, report_json):
    netlist = parse_netlist(netlist_path)
    top = "efuse_otp_array"
    assert masters(netlist, top) == {
        "efuse_rowdrv": ROWS, "efuse_coldrv": COLS, "efuse_row": ROWS, "efuse_sense": 1}, \
        "netlist top no longer matches the floorplan"
    assert masters(netlist, "efuse_row") == {"efuse_bitcell": COLS}, "efuse_row is not 8 bitcells"

    b = Builder(klt, fuse_gds, netlist)
    # Leaf-level subcircuits first, in dependency order.
    for name in ("efuse_bitcell", "efuse_ls", "efuse_rowdrv", "efuse_coldrv",
                 "efuse_comp", "efuse_sense"):
        b.row_cell(name)

    bit_w, bit_h = b.size(b.cells["efuse_bitcell"])
    rd_w, rd_h = b.size(b.cells["efuse_rowdrv"])
    cd_w, cd_h = b.size(b.cells["efuse_coldrv"])
    sa_w, sa_h = b.size(b.cells["efuse_sense"])
    pitch_x = max(bit_w, cd_w) + GAP_UM  # bit lines line up with the column drivers
    pitch_y = max(bit_h, rd_h) + GAP_UM  # word lines line up with the row drivers

    # efuse_row: 8 bitcells at the column pitch (one array instance).
    row = b.layout.create_cell("efuse_row")
    b.place(row, b.cells["efuse_bitcell"], 0.0, 0.0, 1, COLS, pitch_x)
    b.cells["efuse_row"] = row

    t = b.layout.create_cell(top)
    b.place(t, row, 0.0, 0.0, ROWS, 1, 0.0, pitch_y)
    b.place(t, b.cells["efuse_rowdrv"], -(rd_w + GAP_UM), 0.0, ROWS, 1, 0.0, pitch_y,
            away_x=False)
    b.place(t, b.cells["efuse_coldrv"], 0.0, -(cd_h + GAP_UM), 1, COLS, pitch_x,
            away_y=False)
    b.place(t, b.cells["efuse_sense"], 0.0, -(cd_h + GAP_UM + sa_h + GAP_UM), away_y=False)

    verify_fuse(b.layout, "efuse_bitcell__Xf", fuse_gds)

    opts = kdb.SaveLayoutOptions()
    opts.format = "GDS2"
    opts.gds2_write_timestamps = False
    opts.gds2_libname = "efuse_otp_array"
    b.layout.write(str(out_gds), opts)

    bb = t.bbox()
    report = {
        "top_cell": top,
        "dbu_um": DBU_UM,
        "bbox_um": [round(v * DBU_UM, 4) for v in (bb.left, bb.bottom, bb.right, bb.top)],
        "array": {"rows": ROWS, "cols": COLS, "pitch_x_um": round(pitch_x, 4),
                  "pitch_y_um": round(pitch_y, 4)},
        "caveat": "placed hierarchy only: no routing, no connectivity, no DRC/LVS claim",
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
