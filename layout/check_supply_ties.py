# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "klayout-tools @ git+https://github.com/2AMLogic/klayout-tools.git@25da22a118053b44429be544e0ff0573250f8170",
#   "klayout==0.30.14",
# ]
# ///
"""Replay the supply tie checks and their physical failure controls."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import NamedTuple

import klayout.db as kdb

ROOT = Path(__file__).resolve().parents[1]
ARRAY = Path("layout/efuse_otp_array.gds")
SPEC = Path("layout/erc-array.spec.json")
REPORT = Path("layout/erc-array-ties.report.json")
KLT = Path(sys.executable).with_name("klt")


class Partition(NamedTuple):
    top: str
    spec: Path
    rails: set
    ties: set


ANALOG = Partition("efuse_otp_array", SPEC, {"vdd33", "vprog", "vss"},
                   {"nwell_vdd33", "nwell_vprog", "psub_vss"})
DIGITAL = Partition("efuse_otp_ctrl", Path("layout/erc-ctrl.spec.json"), {"VDD", "VSS"},
                    {"nwell_vdd", "psub_vss"})


def check(stream, expected=None, count=1, boxes=None, partition=ANALOG):
    command = [KLT, "erc", stream, partition.spec, "--top", partition.top, "--deck",
               "gf180mcu", "--findings-only", "--omit-antenna-tables", "--format", "json"]
    run = subprocess.run(command, capture_output=True, text=True)
    # The findings-only connectivity run omits antenna grading (exit 4).
    if run.returncode != (3 if expected else 4):
        raise ValueError(f"{stream}: ERC exit {run.returncode}: {run.stderr or run.stdout}")
    report = json.loads(run.stdout)
    coverage = report["erc_coverage"]
    checked = {name for name in partition.ties
               if f'erc.missing_tie:["{name}"]' in coverage["checked"]}
    if (coverage["scope"] != "connectivity" or not coverage["known"] or
            checked != partition.ties or coverage["skipped"] or coverage["inapplicable"] or coverage["unknown"]):
        raise ValueError(f"{stream}: incomplete coverage of supply ties: {coverage}")
    islands = {entry["name"]: entry["matched_islands"] for entry in report["nets"]}
    if islands != dict.fromkeys(partition.rails, 1):
        raise ValueError(f"{stream}: unexpected supply connectivity {islands}")
    findings = [(f["rule"], f["net"], f["other_net"], f["layer"], f.get("via"))
                for f in report["erc_findings"]]
    counts = Counter(findings)
    if (counts != (Counter({expected: count}) if expected else Counter()) or
            report["erc_finding_count"] != len(findings) or
            report["erc_status"] != ("violations" if expected else "clean")):
        raise ValueError(f"{stream}: unexpected ERC findings {counts}")
    if boxes is not None:
        actual = {tuple(f["bbox"][edge] for edge in ("left", "bottom", "right", "top"))
                  for f in report["erc_findings"]}
        if actual != boxes:
            raise ValueError(f"{stream}: missing-tie findings do not locate the disconnected wells")
    print(f"{stream.name}: one island per rail, {len(checked)} checked ties, findings {dict(counts)}")
    return run.stdout


def region(cell, layer):
    index = cell.layout().layer(layer, 0)
    return kdb.Region(cell.begin_shapes_rec(index)).merged()


def contact_controls(directory, top, domains, write, partition):
    layout = top.layout()
    all_cuts = region(top, 33)
    cut_shapes = top.shapes(layout.layer(33, 0))
    for rail, tie, taps, bodies in domains:
        cuts = (all_cuts & taps).merged()
        if taps.is_empty() or cuts.is_empty():
            raise ValueError(f"no drawn taps or contact cuts for {rail}")
        print(f"{rail}: opening {cuts.count()} cuts in {taps.count()} tap footprints")
        cut_shapes.clear()
        cut_shapes.insert(all_cuts - cuts)
        boxes = None
        if bodies is not None:
            boxes = {(b.left, b.bottom, b.right, b.top) for b in
                     (polygon.bbox() for polygon in bodies.each())}
        expected = ("erc.missing_tie", rail, None, tie, None)
        path = directory / f"open-{rail}-contacts.gds"
        layout.write(str(path), write)
        check(path, expected, len(boxes) if boxes else 1, boxes, partition)


def controller_controls(directory):
    layout = kdb.Layout()
    stream = Path("layout/efuse_otp_ctrl.gds")
    check(stream, partition=DIGITAL)
    layout.read(str(stream))
    top = layout.top_cell()
    layout.flatten(top.cell_index(), -1, True)
    write = kdb.SaveLayoutOptions()
    write.gds2_write_timestamps = False
    flat = directory / "ctrl-flat.gds"
    layout.write(str(flat), write)
    check(flat, partition=DIGITAL)
    wells = region(top, 21)
    active = region(top, 22)
    domains = [
        ("VDD", "nwell_vdd", active & region(top, 32) & wells, wells),
        ("VSS", "psub_vss", (active & region(top, 31)) - wells, None),
    ]
    contact_controls(directory, top, domains, write, DIGITAL)


def physical_controls(directory):
    layout = kdb.Layout()
    layout.read(str(ARRAY))
    top = layout.top_cell()

    # Break the native substrate contact by removing only P+ active outside
    # drawn n-wells. Verify the corresponding unchanged, flattened control.
    layout.flatten(top.cell_index(), -1, True)

    active = region(top, 22)
    wells = region(top, 21)
    substrate_taps = (active & region(top, 31)) - wells
    write = kdb.SaveLayoutOptions()
    write.gds2_write_timestamps = False

    def save(name):
        path = directory / name
        layout.write(str(path), write)
        return path

    check(save("flat.gds"))
    active_shapes = top.shapes(layout.layer(22, 0))
    active_shapes.clear()
    active_shapes.insert(active - substrate_taps)
    missing_substrate = ("erc.missing_tie", "vss", None, "psub_vss", None)
    check(save("missing-substrate.gds"), missing_substrate)
    active_shapes.clear()
    active_shapes.insert(active)

    # Keep every active, implant and metal shape. Open only the contact cuts
    # beneath the taps in one voltage class at a time. Each affected n-well
    # must receive its own finding at that well's actual bounding box.
    high_voltage = wells.interacting(region(top, 55))
    normal_voltage = wells - high_voltage
    well_taps = active & region(top, 32)
    domains = [
        ("vdd33", "nwell_vdd33", well_taps & normal_voltage, normal_voltage),
        ("vprog", "nwell_vprog", well_taps & high_voltage, high_voltage),
        ("vss", "psub_vss", substrate_taps, None),
    ]
    contact_controls(directory, top, domains, write, ANALOG)

    # A single M4 rectangle spans the 2 µm gap between the south supply buses.
    layout = kdb.Layout()
    layout.read(str(ARRAY))
    top = layout.top_cell()
    bridge = kdb.DBox(100, -92.5, 101, -89.5).to_itype(layout.dbu)
    contacts = (region(top, 46) & kdb.Region(bridge)).merged()
    if contacts.count() != 2:
        raise ValueError("M4 bridge must overlap both separated buses before insertion")
    top.shapes(layout.layer(46, 0)).insert(bridge)
    layout.write(str(directory / "supply-short.gds"), write)
    check(directory / "supply-short.gds", ("erc.supply_short", "vprog", "vss", None, "metal"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--controller-contacts", action="store_true",
                      help="replay controller cuts using the released klt from layout/erc.sh")
    mode.add_argument("--write", action="store_true", help="refresh the committed intact report")
    args = parser.parse_args()
    os.chdir(ROOT)
    with TemporaryDirectory() as scratch:
        if args.controller_contacts:
            controller_controls(Path(scratch))
            return
        intact = check(ARRAY)
        physical_controls(Path(scratch))
    if args.write:
        REPORT.write_text(intact)
    else:
        subprocess.run([KLT, "erc", "--check", REPORT, "--rerun"], check=True)


if __name__ == "__main__":
    main()
