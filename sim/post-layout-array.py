#!/usr/bin/env python3
"""Measure selected row 31, column 0 in the real 47-port array (fuse-aware tool trial)."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from itertools import product
import json
import math
import os
from pathlib import Path
import re
import subprocess

from lib.pex_pdk import MODEL_DIR, pin_check
from lib.sense_decision import decide

ROOT = Path(__file__).resolve().parents[1]
KLT_SOURCE = "klayout-tools @ git+https://github.com/2AMLogic/klayout-tools.git@25da22a118053b44429be544e0ff0573250f8170"
PINNED_ENGINE = "klayout==0.30.14"
GDS = Path("layout/efuse_otp_array.gds")
CONTROL = Path("layout/.klt/sense-pex/metal-control/array.gds")
WORK = Path("layout/.klt/array-pex")
FUSE = re.compile(r"^(\* device instance \$\d+ r0 \*1 955\.99,683\.06 efuse\n)"
                  r"R\$\d+( (bl\|bl\[0\](?:__t\d+)?) (n(?:__t\d+)?|n\$\d+(?:__t\d+)?) 199\.9998 efuse L=1\.26U W=0\.18U)$", re.M)


def reference():
    source = Path("design/efuse_otp_array.spice").read_text().splitlines()
    start = source.index("**.subckt efuse_otp_array")
    source[start] = source[start][2:]
    it = start + 1
    pins = []
    while source[it].startswith("*+ "):
        source[it] = source[it][1:].replace(",", " ")
        pins.extend(source[it][1:].split())
        it += 1
    if len(pins) != 47 or len(set(pins)) != 47:
        raise ValueError("expected 47 distinct array ports in xschem order")
    source[source.index("**.ends")] = ".ends"
    return pins, "\n".join(line for line in source if line.strip().lower() != ".end") + "\n"


def selected_fuse(netlist, out, schematic):
    if schematic:
        return netlist, "r.xdut.xarr[31].xb[0].xxf.rfuse", ("bl[0]", "xarr[31].xb[0].n")
    text = netlist.read_text()
    if len(re.findall(r"^R\$\d+ .* efuse L=1\.26U W=0\.18U$", text, re.M)) != 256:
        raise ValueError("this PEX netlist must contain all 256 recognized fuses")
    target = FUSE.search(text)
    if not target:
        raise ValueError("the expected far-row fuse lost its physical position or terminal connectivity")
    # '$' is expanded by the ngspice control interpreter. Rename only this
    # resistor designator so 'alter' addresses one element without quoting.
    result, count = FUSE.subn(r"\1Rprogram_target\2", text)
    if count != 1:
        raise ValueError(f"expected one selected fuse, found {count}")
    path = out / "selected-array.spice"
    path.write_text(result)
    return path, "r.xdut.rprogram_target", (target[3], target[4])


def corner_id(config):
    mode, process, temp, logic, resistance = config
    return f"{mode}/{process}/{temp}C/{logic}V/{resistance}ohm"


def configurations(full):
    if full:
        configs = []
        corners = product(("typical", "ss", "ff", "fs", "sf"),
                          (-40, 25, 125), (2.97, 3.3, 3.63))
        for corner in corners:
            configs.extend(("read", *corner, value) for value in (140, 200, 260, 630, 900, 1_000_000_000))
            configs.extend(("program", *corner, value) for value in (140, 200, 260))
    else:
        configs = [("read", process, temp, logic, value)
                   for process, temp, logic in (("ss", -40, 2.97), ("typical", 25, 3.3))
                   for value in (260, 630)]
        configs.extend(("program", "ss", 125, 2.97, value) for value in (140, 200, 260))
    configs.extend((mode, "ss", 125, 2.97, 260) for mode in ("other-row", "other-column"))
    return configs


def check_matrix(report, full):
    metrics = {
        "read": ("preedge_margin_v", "cp_minus_cn_v", "sense_out_v"),
        "program": ("program_current_ma",),
        "other-row": ("deselected_current_ua",),
        "other-column": ("deselected_current_ua",),
    }
    expected = {(corner_id(config), metric) for config in configurations(full) for metric in metrics[config[0]]}
    measured = [(row["corner_id"], row["spec_row"]) for row in report["delta"]]
    if set(measured) != expected or len(measured) != len(expected):
        raise ValueError("incomplete, repeated or unexpected full-array measurement rows")


def bench(config, out, path, target, ends, pins, schematic):
    mode, process, temp, logic, r = config
    name = corner_id(config)
    work = out / name
    work.mkdir(parents=True, exist_ok=True)
    read = mode == "read"
    rail = 5.0 if read else {2.97: 4.5, 3.3: 5.0, 3.63: 5.5}[logic]
    resistor = {"ff": "res_ff", "ss": "res_ss"}.get(process, "res_typical")
    lib = MODEL_DIR / "sm141064.ngspice"
    deck = ["* Row 31, column 0 of the routed 32 x 8 array", f'.include "{MODEL_DIR}/design.ngspice"',
            f'.lib "{lib}" {process}', f'.lib "{lib}" {resistor}']
    if not schematic:
        # The extractor supplies the intact resistance of each drawn link.
        # ngspice accepts the physical L/W card with a neutral resistor model.
        deck.append(".model efuse R()")
    deck.extend([f'.include "{path}"', f"Vlogic vdd33 0 {logic}", f"Vprog vprog 0 {rail}",
                 f"Rstb prog_strobe {'0' if read else 'vdd33'} 1",
                 f"Rsen sense_en {'vdd33' if read else '0'} 1", "Rsense sense_out 0 1G",
                 "Bclk clk 0 V=v(vdd33)*min(max((time-15n)/200p,0),1)" if read else "Rclk clk 0 1"])
    active_row = "row_sel[30]" if mode == "other-row" else "row_sel[31]"
    active_col = "col_sel[1]" if mode == "other-column" else "col_sel[0]"
    for pin in pins:
        if pin.startswith(("row_sel", "col_sel")):
            supply = "vdd33" if pin in (active_row, active_col) else "0"
            deck.append(f"R{pin} {pin} {supply} 1")
    nodes = " ".join("0" if pin == "vss" else pin for pin in pins)
    deck.extend([f"Xdut {nodes} efuse_otp_array", f".temp {temp}", ".control", "set numdgt=12",
                 f"alter {target}={r}"])
    if read:
        sense = ("xdut.sbl", "xdut.xsa.sref", "xdut.xsa.cp", "xdut.xsa.cn") if schematic else (
                 "xdut.inn|sbl", "xdut.inp|sref", "xdut.cp|outp", "xdut.cn|outn")
        deck.append("tran 20p 40n")
        for nodename, signal, time in zip((*sense, "sense_out"), ("sbl", "sref", "cp", "cn", "sout"),
                                          ("14.9n", "14.9n", "38n", "38n", "38n")):
            deck.append(f'meas tran m_{signal} find v("{nodename}") at={time}')
    else:
        deck.extend(["op", f'let m_current = (v("xdut.{ends[0]}")-v("xdut.{ends[1]}"))/{r}',
                     "print m_current"])
    cir = work / "bench.cir"
    cir.write_text("\n".join(deck + ["quit", ".endc", ".end", ""]))
    log = work / "bench.log"
    subprocess.run(["ngspice", "-b", "-o", log, cir], check=True, stdout=subprocess.DEVNULL, timeout=300)
    transcript = log.read_text()
    if re.search(r"^(?:error|fatal|timestep too small)\b", transcript, re.I | re.M):
        raise ValueError(f"ngspice error: {log}")
    x = {name: float(value) for name, value in re.findall(r"^m_(\w+)\s*=\s*([-+.0-9eE]+)", transcript, re.M)}
    if set(x) != ({"sbl", "sref", "cp", "cn", "sout"} if read else {"current"}) or not all(map(math.isfinite, x.values())):
        raise ValueError(f"incomplete measurements: {log}")
    if read:
        prog = r >= 630
        margin = (x["sbl"] - x["sref"]) * (1 if prog else -1)
        resolved, _, correct = decide(x["cp"], x["cn"], x["sout"], logic, int(prog))
        values = [("preedge_margin_v", margin, margin > 0), ("cp_minus_cn_v", x["cp"] - x["cn"], resolved),
                  ("sense_out_v", x["sout"], correct)]
    elif mode == "program":
        values = [("program_current_ma", 1000 * x["current"], x["current"] >= 0.010)]
    else:
        # Identification control: selecting a different row/column must remove
        # at least 99.9% of the 10 mA target from this same physical fuse.
        values = [("deselected_current_ua", 1e6 * x["current"], abs(x["current"]) < 10e-6)]
    return {"corner_id": name, "measurements": [
        {"name": name, "value": value, "status": "pass" if valid else "fail"} for name, value, valid in values]}


def measure(netlist, full):
    side = os.environ["KLT_PEX_SIDE"]
    if side not in {"schematic", "extracted"}:
        raise ValueError(f"unexpected measurement side {side}")
    out = Path(os.environ["KLT_PEX_ARTIFACTS_DIR"]).resolve()
    pins, _ = reference()
    schematic = side == "schematic"
    path, target, ends = selected_fuse(netlist.resolve(), out, schematic)
    jobs = int(os.environ.get("PEX_JOBS", "6" if full else "2"))
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        rows = list(pool.map(lambda config: bench(config, out, path, target, ends, pins, schematic),
                             configurations(full)))
    print(json.dumps({"corners": rows}, allow_nan=False))


def replay(control, full):
    work = WORK / (("metal-control" if control else "baseline") + ("-full" if full else ""))
    work.mkdir(parents=True, exist_ok=True)
    pins, source = reference()
    ref = work / "reference.spice"
    ref.write_text(source)
    version = json.loads(Path("sim/pdk.json").read_text())
    pin_check()
    command = "python3 sim/post-layout-array.py --measure"
    if full:
        command = "python3 sim/post-layout-array.py --full-grid --measure"
    args = ["uvx", "--from", KLT_SOURCE, "--with", PINNED_ENGINE, "klt", "pex", str(CONTROL if control else GDS),
            "--deck", "gf180mcu", "--top", "efuse_otp_array", "--pins", ",".join(pins), "--rename-declared-pins",
            "--pdk", "gf180mcuD", "--pdk-root", str(MODEL_DIR.parents[2]), "--reference-netlist", str(ref),
            "--measure-command", command, "--measure-timeout-s", "14400" if full else "2100",
            "-o", str(work / "array.spice"), "--outdir", str(work / "run"), "--format", "json"]
    run = subprocess.run(args, text=True, stdout=subprocess.PIPE)
    if run.returncode not in {0, 3}:
        raise RuntimeError(f"klt pex exited {run.returncode}")
    report = json.loads(run.stdout)
    check_matrix(report, full)
    if (report["errored"] or report["unfinished"] or
            report["body_bias"]["status"] != "biased" or report["extraction"]["device_count"] != 2393 or
            report["extraction"]["net_count"] != 485 or
            report["provenance"]["pdk"]["version"] != "open_pdks " + version["open_pdks_revision"]):
        raise ValueError("incomplete or incorrectly scoped full-array PEX report")
    output = work / "pex.report.json"
    output.write_text(run.stdout)
    print(f"{output}: {report['status']}, {report['failed']} failed measurement rows")
    return run.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measure", type=Path, metavar="NETLIST", help=argparse.SUPPRESS)
    parser.add_argument("--geometry-control", action="store_true", help="use the refilled scratch GDS with the CN extension removed")
    parser.add_argument("--full-grid", action="store_true", help="run all 45 PVT corners with six read and three program resistances")
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.measure:
        measure(args.measure, args.full_grid)
    else:
        raise SystemExit(replay(args.geometry_control, args.full_grid))
