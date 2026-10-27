"""Build and run the cocotb bench for rtl/efuse_otp_ctrl.v on Icarus.

  python runner.py                     all parameter sets; exit 0 iff all pass
  python runner.py --negative-control  run deliberately broken RTL mutants;
                                       exit 0 iff each mutant is caught by the
                                       check named for it
  python runner.py --emit-klt-requests DIR
                                       write one `klt functional-verification`
                                       request per CONFIGS row into DIR and print
                                       "name rows cols pulse settle" per row

Results (build dirs, results.xml) go under verification/build/ (gitignored).
"""
import argparse
import json
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
RTL = HERE.parent / "rtl" / "efuse_otp_ctrl.v"
BUILD = HERE / "build"
TOP = "efuse_otp_ctrl"

CLK = 10_000_000


def cfg(name, rows, cols, aw, pulse_us, expect_n, clk=CLK, settle=4):
    return dict(name=name, rows=rows, cols=cols, aw=aw, pulse_us=pulse_us,
                expect_n=expect_n, clk=clk, settle=settle)


# Pulse width at 10 MHz: 1 us = 10 cycles (min), 10 us = 100 (nominal),
# 100 us = 1000 (max).  The clamp rows check the 1..100 us limits.
CONFIGS = [
    cfg("32x8_min", 32, 8, 8, 1, 10),
    cfg("32x8_nom", 32, 8, 8, 10, 100),
    cfg("32x8_max", 32, 8, 8, 100, 1000),
    cfg("1x8_min", 1, 8, 3, 1, 10),
    cfg("1x8_nom", 1, 8, 3, 10, 100),
    cfg("1x8_max", 1, 8, 3, 100, 1000, settle=1),
    cfg("32x8_clamp_lo", 32, 8, 8, 0, 10, settle=7),
    cfg("32x8_clamp_hi", 32, 8, 8, 500, 1000),
    cfg("32x8_100MHz_max", 32, 8, 8, 100, 10000, clk=100_000_000),
]

# Each mutant edits one line of the RTL and must be caught by the named test.
MUTANTS = [
    ("arming_bypassed", "armed     <= released;", "armed     <= 1'b1;",
     "test_arming_boundary"),
    ("pulse_off_by_one", "cnt    <= PULSE_N - 1;", "cnt    <= PULSE_N;",
     "test_pulse_width_and_selects"),
    ("outputs_not_reset_gated", "assign prog_strobe = prog_q  & ~rst;",
     "assign prog_strobe = prog_q;", "test_reset_mid_pulse"),
]


def klt_request(c):
    """The `klt functional-verification` request for one CONFIGS row."""
    return {
        "engine": "icarus",
        "sources": [str(RTL)],
        "hdl_toplevel": TOP,
        "testbench": {"module": "test_efuse_otp_ctrl", "search_path": str(HERE)},
        "parameters": dict(ROWS=c["rows"], COLS=c["cols"], AW=c["aw"],
                           CLK_HZ=c["clk"], PULSE_US=c["pulse_us"],
                           SETTLE_CYCLES=c["settle"]),
        "options": {"timescale": ["1ns", "1ps"], "build_args": ["-g2001"],
                    "random_seed": 1},
    }


def emit_klt_requests(outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for c in CONFIGS:
        (outdir / f"fv-{c['name']}.json").write_text(
            json.dumps(klt_request(c), indent=2) + "\n")
        print(c["name"], c["rows"], c["cols"], c["expect_n"], c["settle"])


def run_cfg(c, rtl, tag):
    bdir = BUILD / f"{tag}_{c['name']}"
    shutil.rmtree(bdir, ignore_errors=True)
    params = dict(ROWS=c["rows"], COLS=c["cols"], AW=c["aw"],
                  CLK_HZ=c["clk"], PULSE_US=c["pulse_us"],
                  SETTLE_CYCLES=c["settle"])
    from cocotb_tools.runner import get_runner  # not needed to emit requests
    runner = get_runner("icarus")
    runner.build(verilog_sources=[rtl], hdl_toplevel=TOP, parameters=params,
                 build_dir=bdir, build_args=["-g2001"], timescale=("1ns", "1ps"),
                 always=True)
    xml = runner.test(
        hdl_toplevel=TOP, test_module="test_efuse_otp_ctrl", test_dir=HERE,
        build_dir=bdir, results_xml=str(bdir / "results.xml"),
        extra_env=dict(EFUSE_ROWS=str(c["rows"]), EFUSE_COLS=str(c["cols"]),
                       EFUSE_PULSE_N=str(c["expect_n"]),
                       EFUSE_SETTLE_N=str(c["settle"])))
    passed, failed = [], []
    for case in ET.parse(xml).getroot().iter("testcase"):
        bad = case.find("failure") is not None or case.find("error") is not None
        (failed if bad else passed).append(case.get("name"))
    return passed, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--negative-control", action="store_true")
    ap.add_argument("--emit-klt-requests", metavar="DIR")
    args = ap.parse_args()
    if args.emit_klt_requests:
        emit_klt_requests(args.emit_klt_requests)
        return 0
    BUILD.mkdir(exist_ok=True)

    if not args.negative_control:
        bad = 0
        for c in CONFIGS:
            passed, failed = run_cfg(c, RTL, "rtl")
            status = "PASS" if not failed else "FAIL"
            print(f"[{status}] {c['name']}: {len(passed)} passed, {len(failed)} failed {failed}")
            bad += bool(failed) or not passed
        print("ALL CHECKS PASSED" if not bad else f"{bad} configuration(s) FAILED")
        return 1 if bad else 0

    src = RTL.read_text()
    c = CONFIGS[1]  # 32x8 nominal
    escaped = 0
    for name, old, new, must_fail in MUTANTS:
        if src.count(old) != 1:
            print(f"[ERROR] mutant {name}: pattern not found exactly once in RTL")
            return 2
        mdir = BUILD / f"mutant_{name}"
        shutil.rmtree(mdir, ignore_errors=True)
        mdir.mkdir(parents=True)
        mrtl = mdir / RTL.name
        mrtl.write_text(src.replace(old, new))
        passed, failed = run_cfg(c, mrtl, f"mutant_{name}_run")
        caught = must_fail in failed
        print(f"[{'CAUGHT' if caught else 'ESCAPED'}] mutant {name}: "
              f"{must_fail} {'failed as required' if caught else 'did NOT fail'}")
        escaped += not caught
    if escaped:
        print(f"NEGATIVE CONTROL FAILED: {escaped} broken variant(s) passed the bench")
        return 1
    print("NEGATIVE CONTROL OK: every broken variant was caught")
    return 0


if __name__ == "__main__":
    sys.exit(main())
