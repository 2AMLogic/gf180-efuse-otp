"""Build and run the cocotb bench for rtl/efuse_otp_ctrl.v on Icarus.

  python runner.py                     all parameter sets; exit 0 iff all pass
  python runner.py --negative-control  run deliberately broken RTL mutants;
                                       exit 0 iff each mutant is caught by the
                                       check named for it
  python runner.py --reports DIR       keep each set's klt report as
                                       DIR/<name>.report.json (this is how the
                                       committed sim/controller-fv/ reports are
                                       produced); the negative control always
                                       writes under verification/build/

Every run goes through `klt functional-verification` from the pinned klt
(signoff/klt-pin.txt), with the pinned cocotb supplied to klt's throwaway
environment from requirements.txt -- one execution path, so the reports CI
gates on and the reports committed under sim/controller-fv/ come from the same
code. Reports and run artifacts default to verification/build/ (gitignored).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RTL = ROOT / "rtl" / "efuse_otp_ctrl.v"
BUILD = HERE / "build"
PIN = ROOT / "signoff" / "klt-pin.txt"
REQUIREMENTS = HERE / "requirements.txt"
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


def klt_request(c, rtl=RTL):
    """The `klt functional-verification` request for one CONFIGS row."""
    return {
        "engine": "icarus",
        "sources": [str(rtl)],
        "hdl_toplevel": TOP,
        "testbench": {"module": "test_efuse_otp_ctrl", "search_path": str(HERE)},
        "parameters": dict(ROWS=c["rows"], COLS=c["cols"], AW=c["aw"],
                           CLK_HZ=c["clk"], PULSE_US=c["pulse_us"],
                           SETTLE_CYCLES=c["settle"]),
        "options": {"timescale": ["1ns", "1ps"], "build_args": ["-g2001"],
                    "random_seed": 1},
    }


def run_cfg(c, rtl, tag, outdir, reqdir):
    """Run one parameter set through the pinned `klt functional-verification`.

    Writes the request to reqdir/fv-<tag>.json and the klt report verbatim to
    outdir/<tag>.report.json (run artifacts to outdir/<tag>/), and returns the
    (passed, failed) test names read from that report. The expected pulse and
    settle counts reach the bench through the environment, as the testbench
    documents. Raises RuntimeError if klt produced no report: a check that
    cannot run must fail, never look like one that passed.
    """
    reqdir.mkdir(parents=True, exist_ok=True)
    outdir.mkdir(parents=True, exist_ok=True)
    req = reqdir / f"fv-{tag}.json"
    req.write_text(json.dumps(klt_request(c, rtl), indent=2) + "\n")
    artifacts = outdir / tag
    shutil.rmtree(artifacts, ignore_errors=True)
    env = dict(os.environ,
               EFUSE_ROWS=str(c["rows"]), EFUSE_COLS=str(c["cols"]),
               EFUSE_PULSE_N=str(c["expect_n"]), EFUSE_SETTLE_N=str(c["settle"]))
    argv = ["uvx", "--from", PIN.read_text().strip(),
            "--with-requirements", str(REQUIREMENTS),
            "klt", "functional-verification", str(req),
            "-o", str(artifacts), "--format", "json"]
    # klt exits 0 when every test passes and 3 when the report says fail; both
    # print the report on stdout. Any other exit means the run did not happen.
    proc = subprocess.run(argv, cwd=ROOT, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        report = None
    if not isinstance(report, dict) or not isinstance(report.get("tests"), list):
        raise RuntimeError(
            f"klt functional-verification produced no report for {tag} "
            f"(exit {proc.returncode}): {proc.stderr.strip()[-2000:]}")
    (outdir / f"{tag}.report.json").write_text(proc.stdout)
    passed, failed = [], []
    for t in report["tests"]:
        (passed if t.get("status") == "passed" else failed).append(t.get("name"))
    return passed, failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--negative-control", action="store_true")
    ap.add_argument("--reports", metavar="DIR")
    args = ap.parse_args()
    BUILD.mkdir(exist_ok=True)
    reqdir = BUILD / "requests"

    if not args.negative_control:
        outdir = Path(args.reports).resolve() if args.reports else BUILD
        bad = 0
        for c in CONFIGS:
            passed, failed = run_cfg(c, RTL, c["name"], outdir, reqdir)
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
        mdir = BUILD / "mutants" / name
        shutil.rmtree(mdir, ignore_errors=True)
        mdir.mkdir(parents=True)
        mrtl = mdir / RTL.name
        mrtl.write_text(src.replace(old, new))
        passed, failed = run_cfg(c, mrtl, f"mutant_{name}", BUILD, reqdir)
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
