# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "klayout-tools @ git+https://github.com/2AMLogic/klayout-tools.git@25da22a118053b44429be544e0ff0573250f8170",
#   "klayout==0.30.14",
# ]
# ///
"""Replay the fuse-aware candidate on the unchanged routed array and xschem netlist."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

import klayout.db as kdb
from klayout_tools.evidence_canonicalize import canonicalize

ROOT = Path(__file__).resolve().parents[1]
STREAM = Path("layout/efuse_otp_array.gds")
NETLIST = Path("design/efuse_otp_array.spice")
REPORT = Path("layout/lvs-array-fuse-candidate.report.json")
KLT = Path(sys.executable).with_name("klt")


def boundary_pairs():
    # The xschem file comments the top header. Read its pin list, then
    # compare its unmodified devices in .TOP with hard name correspondences.
    lines = NETLIST.read_text().splitlines()
    i = lines.index("**.subckt efuse_otp_array") + 1
    pins = []
    while lines[i].startswith("*+ "):
        pins.extend(lines[i][3:].replace(",", " ").split())
        i += 1
    layout_names = {f"row_sel[{n}]": f"in,row_sel,row_sel[{n}]" for n in range(32)}
    layout_names.update({f"col_sel[{n}]": f"col_sel,col_sel[{n}]" for n in range(8)})
    for name in ("clk", "sense_en", "prog_strobe", "sense_out", "vdd33", "vprog", "vss"):
        layout_names[name] = name
    if len(pins) != len(layout_names) or set(pins) != set(layout_names):
        raise ValueError("schematic boundary differs from the 47 named layout nets")
    return [[drawn, pin.upper()] for pin, drawn in layout_names.items()]


def compare(stream, pairs, expected):
    request = {
        "layout": {"file": str(stream), "top": "efuse_otp_array", "deck": "gf180mcu"},
        "reference": {"netlist": str(NETLIST), "form": "subckt-call", "deck": "gf180mcu",
                      "top": ".TOP"},
        "options": {"anchor_top_level_pins": True, "flatten_reference": [".TOP"],
                    "combine_devices": ["nfet", "pfet"], "compare_parameters": {"ppolyf_u": ["R"]}},
        "hints": {"same_nets": pairs},
        "portable_paths": True,
    }
    run = subprocess.run([KLT, "lvs", "-", "--format", "json"], input=json.dumps(request),
                         capture_output=True, text=True)
    expected_rc = 0 if expected == "match" else 3
    if run.returncode != expected_rc:
        raise RuntimeError(f"{stream}: LVS exit {run.returncode}: {run.stderr or run.stdout[:500]}")
    result = json.loads(run.stdout)
    if result["status"] != expected:
        raise ValueError(f"{stream}: unexpected {result['status']} LVS verdict")
    fuse = [m["details"] for m in result["mismatches"] if
            m["category"] == "device.geometry_not_compared" and m["device"]["class"] == "efuse"]
    if len(fuse) != 1 or (fuse[0]["layout_devices"], fuse[0]["reference_devices"]) != (256, 256):
        raise ValueError("LVS must identify all 256 layout and reference fuses")
    print(f"{stream.name}: {expected}, {result['error_count']} errors, {result['counts']}")
    return result, run.stdout


def short_one_fuse(path):
    layout = kdb.Layout()
    layout.read(str(STREAM))
    top = layout.top_cell()
    row = next(i for i in top.each_inst() if i.cell.name == "efuse_row")
    bit = next(i for i in row.cell.each_inst() if i.cell.name == "efuse_bitcell")
    # Place one shape on the top, over BL and N in one repetition. Modifying
    # the shared bitcell master would short all 256 fuses.
    bridge = row.trans * bit.trans * kdb.DBox(5.0, 2.1, 7.0, 2.3).to_itype(layout.dbu)
    m1 = layout.layer(34, 0)
    metal = kdb.Region(top.begin_shapes_rec(m1)).merged()
    if (metal & kdb.Region(bridge)).merged().count() != 2:
        raise ValueError("single-fuse bridge must reach two separate Metal1 shapes")
    top.shapes(m1).insert(bridge)
    options = kdb.SaveLayoutOptions()
    options.gds2_write_timestamps = False
    layout.write(str(path), options)


def replay_fields(report):
    fresh = canonicalize(report, "lvs")
    # KLayout numbers extracted nets in a host-dependent order. Preserve
    # every row, including which rows share one ID, under a bijective renaming.
    ids = {}
    for net in fresh["net_correspondence"]:
        net["layout_id"] = ids.setdefault(net["layout_id"], len(ids))
    return fresh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="refresh the candidate report")
    args = parser.parse_args()
    os.chdir(ROOT)
    pairs = boundary_pairs()
    intact, output = compare(STREAM, pairs, "match")
    counts = intact["counts"]
    for name in ("nets", "devices"):
        c = counts[name]
        if c["layout"] != c["reference"] or c["matched"] != c["layout"]:
            raise ValueError(f"intact array did not pair every {name} entry: {c}")
    correspondence = {(n["layout"], n["reference"]) for n in intact["net_correspondence"]}
    if intact["error_count"] or any((a.replace(",", "|"), b) not in correspondence for a, b in pairs):
        raise ValueError("intact array did not confirm every named boundary pair")

    with TemporaryDirectory() as scratch:
        path = Path(scratch) / "one-fuse-short.gds"
        short_one_fuse(path)
        short, _ = compare(path, pairs, "mismatch")
    errors = [m for m in short["mismatches"] if m["severity"] == "error"]
    if (short["counts"]["nets"]["layout"] != counts["nets"]["layout"] - 1 or
            not any(m["category"] == "device.unmatched" and m["device"]["class"] == "efuse" and
                    m["device"]["reference"] == "ARR[0]_B[7]_XF" for m in errors) or
            not any(m["category"] == "net.merged" and
                    m["net"]["reference"] == "ARR[0]_B[7]_N" for m in errors)):
        raise ValueError("the physical bridge must identify the affected fuse and its merged net")

    swap = {"SENSE_EN": "PROG_STROBE", "PROG_STROBE": "SENSE_EN"}
    wrong, _ = compare(STREAM, [[a, swap.get(b, b)] for a, b in pairs], "mismatch")
    rejected = {(m["net"]["layout"], m["net"]["reference"]) for m in wrong["mismatches"]
                if m["category"] == "hints.rejected"}
    if rejected != {(a.lower(), b) for a, b in swap.items()}:
        raise ValueError("LVS must reject both swapped boundary constraints")

    if args.write:
        REPORT.write_text(output)
    elif replay_fields(intact) != replay_fields(json.loads(REPORT.read_text())):
        raise ValueError("candidate LVS report differs from the fresh comparison")


if __name__ == "__main__":
    main()
