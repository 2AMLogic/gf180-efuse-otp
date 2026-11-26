#!/usr/bin/env python3
"""Replay the physical-reference sense bench on the routed sense cell with klt pex."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from itertools import product
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

from lib.sense_decision import decide

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = Path(os.environ.get("PDK_ROOT", Path.home() / ".ciel")).resolve() / "gf180mcuD/libs.tech/ngspice"
WORK = Path("layout/.klt/sense-pex")
REPORT = Path("layout/pex-sense.report.json")
GDS = "layout/efuse_otp_array.gds"
ORDER = "sbl,sense_en,clk,sense_out,vdd33,vprog,vss"
TEMPLATE = ROOT / "sim/sense-margin/sense.cir.in"
SOURCE = ROOT / "design/efuse_otp_array.spice"
VALUES = (140, 200, 260, 630, 900, 1000000000)
SIGNALS = ("v_sbl", "v_sref", "v_sense_out", "v_cp", "v_cn")
MEAS = re.compile(r"^(v_sbl|v_sref|v_sense_out|v_cp|v_cn)\s*=\s*([-+Ee.0-9]+)", re.M)


def grid():
    return product(("typical", "ff", "ss", "fs", "sf"), (-40, 25, 125), (2.97, 3.3, 3.63), VALUES)


def point(config, side, netlist, outdir, template):
    process, temp, vdd, rfuse = config
    name = f"{process}/{temp}C/{vdd}V/{rfuse}ohm"
    work = outdir / name
    work.mkdir(parents=True, exist_ok=True)
    resistor = {"ss": "res_ss", "ff": "res_ff"}.get(process, "res_typical")
    models = MODEL_DIR / "sm141064.ngspice"
    deck = template.replace("@DESIGN@", str(MODEL_DIR / "design.ngspice"))
    deck = deck.replace("@RFUSE@", str(rfuse)).replace("Vdd33 vdd33 0 DC 3.3", f"Vdd33 vdd33 0 DC {vdd}")
    # The drawn nets carry both their parent and comparator-pin labels.
    sref, cp, cn = ("sref", "cp", "cn") if side == "schematic" else ("inp|sref", "cp|outp", "cn|outn")
    nodes = ("sbl", "xsa." + sref, "sense_out", "xsa." + cp, "xsa." + cn)
    deck += f'\n.lib "{models}" {process}\n.lib "{models}" {resistor}\n.include "{netlist}"\n.temp {temp}\n'
    deck += ".tran 20p 40n\n"
    for signal, node, at in zip(SIGNALS, nodes, ("14.9n", "14.9n", "38n", "38n", "38n")):
        deck += f".meas tran {signal} find v({node}) at={at}\n"
    deck += ".end\n"
    (work / "bench.cir").write_text(deck)
    log = work / "bench.log"
    subprocess.run(["ngspice", "-b", "-o", log, work / "bench.cir"], check=True,
                   stdout=subprocess.DEVNULL, timeout=90)
    output = log.read_text()
    values = {key: float(value) for key, value in MEAS.findall(output)}
    if set(values) != set(SIGNALS) or not all(math.isfinite(x) for x in values.values()):
        raise ValueError(f"{side}, {name}: incomplete ngspice measurements in {log}")
    programmed = rfuse >= 630
    margin = (1 if programmed else -1) * (values["v_sbl"] - values["v_sref"])
    resolved, _, correct = decide(values["v_cp"], values["v_cn"], values["v_sense_out"], vdd, int(programmed))
    return {"corner_id": name, "measurements": [
        {"name": "margin_v", "value": margin, "status": "pass" if margin > 0 else "fail"},
        {"name": "v_sense_out", "value": values["v_sense_out"], "status": "pass" if correct else "fail"},
        {"name": "latch_cp_minus_cn_v", "value": values["v_cp"] - values["v_cn"],
         "status": "pass" if resolved else "fail"},
    ]}


def measure(netlist):
    side = os.environ["KLT_PEX_SIDE"]
    if side not in {"schematic", "device-only", "extracted"}:
        raise ValueError(f"Unexpected PEX leg {side}")
    template = TEMPLATE.read_text()
    out = Path(os.environ["KLT_PEX_ARTIFACTS_DIR"]).resolve()
    with ThreadPoolExecutor(max_workers=6) as workers:
        corners = list(workers.map(lambda config: point(config, side, netlist, out, template), grid()))
    print(json.dumps({"corners": corners}, allow_nan=False))


def pin_check():
    pin = json.loads((ROOT / "sim/pdk.json").read_text())
    ngspice = subprocess.check_output(["ngspice", "--version"], text=True)
    if not re.search(r"ngspice-" + re.escape(pin["ngspice_version"]) + r"\b", ngspice):
        raise ValueError(f"Use ngspice {pin['ngspice_version']} from sim/pdk.json")
    version_root = MODEL_DIR.parents[2]
    if (version_root / "gf180mcuD/SOURCES").read_text().strip() != "open_pdks " + pin["open_pdks_revision"]:
        raise ValueError("PDK_ROOT must name the open_pdks revision pinned in sim/pdk.json")
    canonical = version_root / pin["variant"] / "libs.tech/ngspice"
    for model_file in pin["fleet_checked_model_files"]:
        if (canonical / model_file).read_bytes() != (MODEL_DIR / model_file).read_bytes():
            raise ValueError(f"gf180mcuD differs from the pinned {pin['variant']} model: {model_file}")


def controls():
    """Change one extracted element at a time. The native report stays intact."""
    netlist = WORK / "sense.spice"
    baseline = netlist.read_text()
    template = TEMPLATE.read_text()
    for name, original, alternate in (
        ("strong-substrate", "Rvsubs_dctie vsubs 0 1e+12", "Rvsubs_dctie vsubs 0 1"),
        ("matched-cp-load", "Ccp_outp cp|outp vsubs 1.6297548e-14", "Ccp_outp cp|outp vsubs 1.3515993e-14"),
    ):
        if baseline.splitlines().count(original) != 1 or "Ccn_outn cn|outn vsubs 1.3515993e-14" not in baseline.splitlines():
            raise ValueError("Selected layout or extracted load changed; inspect the control before repeating it")
        scratch = WORK / "controls" / name
        scratch.mkdir(parents=True, exist_ok=True)
        variant = (scratch / "sense.spice").resolve()
        variant.write_text(baseline.replace(original, alternate))
        if name == "strong-substrate":
            configs = product(("ss",), (-40, 25, 125), (2.97, 3.3, 3.63), (630,))
        else:
            configs = grid()
        with ThreadPoolExecutor(max_workers=6) as workers:
            rows = list(workers.map(lambda config: point(config, "extracted", variant, scratch, template), configs))
        failures = [row["corner_id"] for row in rows if any(m["status"] != "pass" for m in row["measurements"])]
        print(f"{name}: {len(failures)} failing corners of {len(rows)}: {failures}")
        (scratch / "measurements.json").write_text(json.dumps(rows, indent=2) + "\n")


def geometry_control():
    """Add a 36 µm extension to the existing CN Metal2 track in a scratch GDS."""
    import klayout.db as db

    work = WORK / "metal-control"
    work.mkdir(parents=True, exist_ok=True)
    layout = db.Layout()
    layout.read(GDS)
    sense = layout.cell("efuse_sense")
    tracks = sense.shapes(layout.layer(36, 0))
    # The CN gate via attaches at x=131.87 µm to this horizontal Metal2 track.
    track = db.DBox(103.50, 25.34, 143.58, 25.76).to_itype(layout.dbu)
    if len([s for s in tracks.each() if s.is_box() and s.box == track]) != 1:
        raise ValueError("CN Metal2 track moved; inspect the sense layout before repeating this control")
    before = db.Region(tracks).merged()
    extension = db.DBox(67.50, 25.34, 103.60, 25.76).to_itype(layout.dbu)
    tracks.insert(extension)
    change = (before ^ db.Region(tracks)).merged()
    expected = db.DBox(67.50, 25.34, 103.50, 25.76).to_itype(layout.dbu)
    if not (change ^ db.Region(expected)).is_empty():
        raise ValueError("physical control must add exactly 36 × 0.42 µm of Metal2")
    options = db.SaveLayoutOptions()
    options.gds2_write_timestamps = False
    # The original metal fill was placed before the new wire. Re-run the
    # array's normal fill flow so its 2 µm keepout follows the changed route.
    top = layout.cell("efuse_otp_array")
    fill = layout.cell("density_fill")
    instances = [inst for inst in top.each_inst() if inst.cell_index == fill.cell_index()]
    if len(instances) != 1:
        raise ValueError("expected one density_fill instance at the array top")
    instances[0].delete()
    layout.delete_cell(fill.cell_index())
    raw = work / "unfilled.gds"
    layout.write(str(raw), options)
    filled = work / "filled.gds"
    subprocess.run([sys.executable, "layout/fill_partitions.py", "--input", raw, "--output", filled,
                    "--report", work / "fill.json", "--top", "efuse_otp_array"], check=True, stdout=subprocess.DEVNULL)
    stream = work / "array.gds"
    subprocess.run([sys.executable, "layout/order_gds.py", filled, stream], check=True)
    return replay(str(stream), work, work / "pex.report.json")


def replay(gds, work, report_path):
    work.mkdir(parents=True, exist_ok=True)
    reference = work / "sense-reference.spice"
    source = SOURCE.read_text()
    blocks = [re.search(r"^\.subckt " + name + r"\b.*?^\.ends[^\n]*", source, re.M | re.S)
              for name in ("efuse_sense", "efuse_comp")]
    if not all(blocks):
        raise ValueError(f"Missing sense or comparator subcircuit in {SOURCE}")
    reference.write_text("* Physical-reference sense subcircuits from design/efuse_otp_array.spice\n" +
                   "\n".join(block.group() for block in blocks) + "\n")
    pin = Path("signoff/klt-pin.txt").read_text().strip()
    args = ["uvx", "--from", pin, "klt", "pex", gds, "--reference-netlist", str(reference),
            "--measure-command", "python3 sim/post-layout-sense.py --measure", "--measure-timeout-s", "900",
            "--device-only-leg", "--deck", "gf180mcu", "--top", "efuse_sense", "--pins", ORDER,
            "--rename-declared-pins", "--pdk", "gf180mcuD", "--pdk-root", str(MODEL_DIR.parents[2]),
            "-o", str(work / "sense.spice"), "--outdir", str(work / "run"), "--format", "json"]
    run = subprocess.run(args, stdout=subprocess.PIPE, text=True)
    if run.returncode not in {0, 3}:
        raise RuntimeError(f"klt pex exited {run.returncode}")
    report = json.loads(run.stdout)
    if (len(report["delta"]) != 270 * 3 or report["errored"] or report["unfinished"] or
            report["body_bias"]["status"] != "biased" or report["extraction"]["device_count"] != 33 or
            any(row.get("device_only_status") not in {"pass", "fail"} for row in report["delta"])):
        raise ValueError("Incomplete sense PEX report or unexpected cell scope")
    report_path.write_text(run.stdout)
    print(f"{report_path}: {report['status']}, {report['failed']} failing measurement rows")
    return run.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measure", metavar="NETLIST", type=Path, help=argparse.SUPPRESS)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--controls", action="store_true", help="run substrate and matched-load sensitivity controls after replay")
    mode.add_argument("--geometry-control", action="store_true", help="extend the drawn CN route in scratch and replay the unmodified bench")
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.measure:
        measure(args.measure.resolve())
    else:
        pin_check()
        if args.controls:
            controls()
        elif args.geometry_control:
            raise SystemExit(geometry_control())
        else:
            raise SystemExit(replay(GDS, WORK, REPORT))
