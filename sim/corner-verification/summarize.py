#!/usr/bin/env python3
"""Fold the klt sim reports of a corner-verification run into record.json.

Called by run.sh with the record directory. Reads sets/<stem>/report.json for the
three program-current requests (prog_rf<ohm>) and the negative control
(control_rf260_w<width>); a report that never came back, or came back with no
corners or fewer than its corner_count, is refused with exit 4 rather than folded
as a smaller set. Lists every PVT point, names the binding corner (minimum
fuse current) per fuse value, and reports per-row pass/fail. The sense-margin row is
not run here: its verdict is read from the committed sim/sense-margin record and
quoted, never recomputed. Pass/fail is data in the record, not an exit status.
"""
import argparse
import glob
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import bench_record  # noqa: E402  (needs the path insert above under python3 -I)

SENSE_RECORD_GLOB = os.path.join("sim", "sense-margin", "records", "*", "record.json")


def points(report, fuse):
    out = []
    for c in report["corners"]:
        m = {x["name"]: x.get("value") for x in c.get("measurements", [])}
        i = m.get("i_fuse")
        ok = c.get("status") in ("pass", "fail") and i is not None and math.isfinite(i)
        out.append({
            "process": c["process"], "temp_c": c["temperature_c"],
            "vdd33_v": c["supply_v"]["vdd33"], "vprog_v": c["supply_v"]["vprog"],
            "fuse_ohm": fuse, "i_fuse_a": i, "v_wl_v": m.get("v_wl"),
            "v_bl_v": m.get("v_bl"), "v_sel_d_v": m.get("v_sel_d"),
            "status": c.get("status"), "finite": bool(ok),
        })
    return sorted(out, key=lambda p: (p["process"], p["temp_c"], p["vprog_v"]))


def summarize(pts, ireq):
    valid = [p for p in pts if p["finite"]]
    for p in pts:
        p["pass"] = bool(p["finite"] and p["i_fuse_a"] >= ireq)
    bind = min(valid, key=lambda p: p["i_fuse_a"]) if valid else None
    return {
        "points": len(pts), "complete": bool(pts) and len(valid) == len(pts),
        "all_pass": bool(pts) and all(p["pass"] for p in pts),
        "min_i_fuse_a": bind["i_fuse_a"] if bind else None,
        "binding_corner": bind,
        "failing_points": [p for p in pts if not p["pass"]],
        "point_list": pts,
    }


def sense_citation(repo):
    recs = sorted(glob.glob(os.path.join(repo, SENSE_RECORD_GLOB)))
    if not recs:
        return None
    path = recs[-1]
    r = json.load(open(path))
    return {
        "record": os.path.relpath(path, repo),
        "analog_margin_positive_everywhere": r.get("analog_margin_positive_everywhere"),
        "decision_correct_everywhere": r.get("decision_correct_everywhere"),
        "negative_control_flips_sign": (r.get("negative_control") or {}).get("demonstrates_bench_can_fail"),
        "verdict": r.get("verdict"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rec")
    ap.add_argument("--ireq", type=float, required=True)
    ap.add_argument("--rroute", type=float, required=True)
    ap.add_argument("--fuse-ohms", required=True)
    ap.add_argument("--w-control", required=True)
    bench_record.add_common_args(ap)
    a = ap.parse_args()
    repo = os.path.abspath(os.path.join(a.rec, "..", "..", "..", ".."))

    # The requests run.sh submitted, named rather than discovered; load_reports
    # refuses a partial set before any grading, so a report that never came
    # back -- or came back with no corners, or fewer than its corner_count --
    # cannot fold a smaller set into `complete: true`.
    stems = ["prog_rf" + r for r in a.fuse_ohms.split()]
    stems.append("control_rf260_w" + a.w_control)
    reports = bench_record.load_reports(a.rec, stems)
    # The PVT grid the corners actually ran, read back from the reports rather
    # than retyped from decision 0005, so `pvt` cannot contradict point_list.
    process, temp_c, supplies = bench_record.pvt_axes(reports)

    backends, jobs, engines = set(), set(), set()

    def load(stem):
        return bench_record.collect_env(reports[stem], backends, jobs, engines)

    fuses = {}
    for r in a.fuse_ohms.split():
        fuses[r] = summarize(points(load("prog_rf" + r), int(r)), a.ireq)
    ctl = summarize(points(load("control_rf260_w" + a.w_control), 260), a.ireq)
    # The control is valid only if it reads fail and names a binding corner.
    ctl_ok = (not ctl["all_pass"]) and ctl["binding_corner"] is not None

    complete = all(f["complete"] for f in fuses.values())
    all_pass = complete and all(f["all_pass"] for f in fuses.values())
    bind = min((f["binding_corner"] for f in fuses.values() if f["binding_corner"]),
               key=lambda p: p["i_fuse_a"], default=None)
    rec = {
        **bench_record.header(a, backends, jobs, engines),
        "dut": "efuse_coldrv + efuse_rowdrv (each with efuse_ls) + efuse_bitcell, extracted from design/efuse_otp_array.spice; one selected cell",
        "corners": "%d per request: %d process x %d temperature x %d supply pair (decision 0005); see pvt"
                   % (len(process) * len(temp_c) * len(supplies),
                      len(process), len(temp_c), len(supplies)),
        # The zipped (vdd33, vprog) pairs as the committed records spell them:
        # vdd33 in the decision-0005 two-decimal notation, vprog as parsed.
        "pvt": {"process": process, "temp_c": temp_c,
                "supplies_v": "vdd33 and vprog step together (klt sim zips supply_v axes): "
                              + ", ".join("(%.2f, %s)" % (s["vdd33"], s["vprog"])
                                          for s in supplies),
                "source": "decision 0005"},
        "requirement": {"i_fuse_min_a": a.ireq, "source": "assumption A2, spec/efuse-otp.md section 2 (no PDK source)"},
        "assumptions": {
            "routing_resistance_ohm": {"value": a.rroute, "status": "assumption, no documented source (same lumped value as sim/program-select)"},
            "fuse_140_260_ohm": "plain resistor replacing the efuse in a copy of efuse_bitcell (select device unchanged); 200 ohm uses the committed efuse_bitcell with the PDK efuse model (pblow=0). A4 range; only 200 ohm is documented.",
            "array_loading": "one selected cell; unselected-cell leakage on the bitline and word-line capacitance are not modelled (DC operating point)",
            "supply_combinations": "vdd33 and vprog move together; mixed combinations (e.g. vprog low with vdd33 high) are not covered",
        },
        "complete": complete,
        "fuses": fuses,
        "row_program_current": {
            "spec_row": "P06 / claim C1", "all_pass": all_pass,
            "binding_corner": bind,
            "min_i_fuse_a": bind["i_fuse_a"] if bind else None,
        },
        "negative_control": {
            "description": "select narrowed to %s at the 260 ohm fuse; must read fail" % a.w_control,
            "all_pass": ctl["all_pass"], "reads_fail": not ctl["all_pass"],
            "binding_corner": ctl["binding_corner"], "valid": ctl_ok,
            "min_i_fuse_a": ctl["min_i_fuse_a"],
        },
        "row_sense_margin": sense_citation(repo),
        "verdict": ("program current: %s over the decision-0005 grid%s; negative control %s. Sense row: see row_sense_margin (cited, not re-run)."
                    % ("PASS" if all_pass else "FAIL",
                       "" if not bind else " (binding corner %s %s C vdd33 %s V vprog %s V fuse %s ohm, %.4g mA)" % (
                           bind["process"], bind["temp_c"], bind["vdd33_v"], bind["vprog_v"], bind["fuse_ohm"], bind["i_fuse_a"] * 1e3),
                       "valid (reads fail)" if ctl_ok else "NOT VALID (did not read fail)")),
    }
    bench_record.write_record(a.rec, rec)
    if not complete:
        print("incomplete: some points have no current (see sets/*/report.json diagnostics)")
        raise SystemExit(3)


if __name__ == "__main__":
    main()
