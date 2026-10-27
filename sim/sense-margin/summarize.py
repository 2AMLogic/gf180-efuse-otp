#!/usr/bin/env python3
"""Fold the per-fuse-value klt sim reports of a sense-margin run into record.json.

Called by run.sh with the record directory. Reads sets/<stem>/report.json for the
bench requests (bench_rf<ohm|open>_rr<ref>) and the negative control
(control_rf<ohm>_rr<ref>). Per PVT point:

  margin_v          v(sbl) - v(sref) just before the clock edge (programmed fuse
                    should read positive, intact negative)
  signed_margin_v   margin_v for a programmed fuse, -margin_v for an intact one;
                    positive = the correct side of the reference
  resolved          |v(cp) - v(cn)| >= 0.5 * vdd33 after the clock edge (the
                    comparator reached a decision rather than an intermediate level)
  decision_bit      1 if v(sense_out) >= 0.7 * vdd33, 0 if <= 0.3 * vdd33, else None
  decision_ok       decision_bit equals the expected bit (programmed = 1, intact = 0)
                    AND the comparator resolved

Pass/fail is data here, not an exit status. The negative control flips sign when some
intact control point reads the wrong side while the same bench corner read the right one.
"""
import argparse
import glob
import json
import math
import os
import re


def finite(x):
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


def load(rec, pattern):
    out = {}
    for path in sorted(glob.glob(os.path.join(rec, "sets", pattern, "report.json"))):
        out[os.path.basename(os.path.dirname(path))] = json.load(open(path))
    return out


def points(rep, rfuse, programmed):
    pts = []
    for c in rep["corners"]:
        m = {x["name"]: x.get("value") for x in c.get("measurements", [])}
        sbl, sref, so = m.get("v_sbl"), m.get("v_sref"), m.get("v_sense_out")
        cp, cn, vdd = m.get("v_cp"), m.get("v_cn"), c["supply_v"]["vdd33"]
        ok = all(finite(v) for v in (sbl, sref, so, cp, cn))
        margin = (sbl - sref) if ok else None
        signed = (margin if programmed else -margin) if ok else None
        resolved = bool(ok and abs(cp - cn) >= 0.5 * vdd)
        bit = None
        if ok:
            bit = 1 if so >= 0.7 * vdd else (0 if so <= 0.3 * vdd else None)
        exp = 1 if programmed else 0
        pts.append({
            "process": c["process"], "temp_c": c["temperature_c"], "vdd33_v": vdd,
            "rfuse_ohm": rfuse, "status": c.get("status"),
            "margin_v": margin, "signed_margin_v": signed,
            "v_sense_out": so, "v_cp": cp, "v_cn": cn,
            "resolved": resolved, "decision_bit": bit, "expected_bit": exp,
            "decision_ok": bool(ok and resolved and bit == exp),
        })
    return pts


def key(p):
    return (p["process"], p["temp_c"], p["vdd33_v"])


def per_fuse(pts):
    valid = [p for p in pts if finite(p["signed_margin_v"])]
    bind = min(valid, key=lambda p: p["signed_margin_v"]) if valid else None
    return {
        "points": len(pts),
        "complete": len(valid) == len(pts) and bool(pts),
        "min_signed_margin_v": bind["signed_margin_v"] if bind else None,
        "binding_corner": bind,
        "all_margin_positive": bool(pts) and len(valid) == len(pts) and all(p["signed_margin_v"] > 0 for p in valid),
        "all_decisions_ok": bool(pts) and all(p["decision_ok"] for p in pts),
        "unresolved_points": sum(1 for p in pts if not p["resolved"]),
        "point_list": sorted(pts, key=key),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rec")
    ap.add_argument("--rref", type=float, required=True)
    ap.add_argument("--rref-control", type=float, required=True)
    ap.add_argument("--rfuse-intact", required=True)
    ap.add_argument("--rfuse-programmed", required=True)
    ap.add_argument("--t-pre", required=True)
    ap.add_argument("--t-out", required=True)
    ap.add_argument("--t-edge", required=True)
    ap.add_argument("--pdk-rev", required=True)
    ap.add_argument("--stamp", required=True)
    ap.add_argument("--ngspice", required=True)
    ap.add_argument("--klt", required=True)
    a = ap.parse_args()

    intact = a.rfuse_intact.split()
    programmed = a.rfuse_programmed.split()
    bench, control = {}, {}
    backends, jobs = set(), set()
    reports = load(a.rec, "*")
    for stem, rep in reports.items():
        m = re.match(r"(bench|control)_rf(\w+)_rr(\d+)$", stem)
        if not m:
            continue
        kind, rf, rr = m.group(1), m.group(2), int(m.group(3))
        env = rep.get("environment", {})
        backends.add(json.dumps(env.get("backend", {}), sort_keys=True))
        remote = env.get("remote") or {}
        for k in ("job_id", "job_ids"):
            v = remote.get(k)
            if v:
                jobs.update(v if isinstance(v, list) else [v])
        pts = points(rep, rf, rf in programmed)
        (bench if kind == "bench" else control)[rf] = (rr, pts)

    fuses = {}
    for rf in intact + programmed:
        if rf in bench:
            fuses[rf] = dict(per_fuse(bench[rf][1]), population="programmed (A5)" if rf in programmed else "intact (A4)")

    flips = []
    for rf, (rr, pts) in sorted(control.items()):
        nominal = {key(p): p for p in bench.get(rf, (None, []))[1]}
        for p in pts:
            n = nominal.get(key(p))
            if n and finite(n["signed_margin_v"]) and finite(p["signed_margin_v"]) \
                    and n["signed_margin_v"] > 0 > p["signed_margin_v"]:
                flips.append({"rfuse_ohm": rf, "rref_ohm": rr, "process": p["process"], "temp_c": p["temp_c"],
                              "vdd33_v": p["vdd33_v"], "bench_signed_margin_v": n["signed_margin_v"],
                              "control_signed_margin_v": p["signed_margin_v"]})
    control_ok = bool(flips)

    expected = len(intact) + len(programmed)
    complete = len(fuses) == expected and all(f["complete"] for f in fuses.values()) and bool(control)
    bench_margin_ok = complete and all(f["all_margin_positive"] for f in fuses.values())
    bench_decision_ok = complete and all(f["all_decisions_ok"] for f in fuses.values())

    rec = {
        "pdk_revision": a.pdk_rev,
        "variant_pinned": "gf180mcuC",
        "variant_simulated": "gf180mcuD (fleet image; sm141064.ngspice, sm141064.spice, design.ngspice byte-identical to gf180mcuC, checked by run.sh)",
        "timestamp_utc": a.stamp,
        "ngspice_version_local": a.ngspice,
        "klt_version": a.klt,
        "backend": [json.loads(b) for b in sorted(backends)],
        "remote_job_ids": sorted(jobs),
        "dut": "efuse_sense (with efuse_comp), extracted from design/efuse_otp_array.spice",
        "pvt": {"process": ["typical", "ff", "ss", "fs", "sf"], "temp_c": [-40, 25, 125],
                "vdd33_v": [2.97, 3.30, 3.63], "source": "decision 0005"},
        "assumptions": {
            "intact_range_ohm": {"value": [float(x) for x in intact], "status": "assumption A4; only the 200 ohm point is documented (+/-30% is the assumed range)"},
            "programmed_range_ohm": {"value": ["630", "900", "open (1 Gohm)"], "status": "assumption A5; only the 900 ohm point is documented (-30% is the assumed lower edge)"},
            "reference_ohm": {"value": a.rref, "status": "assumption A6 (decision 0003); geometric midpoint of 200/900 is ~424 ohm"},
            "fuse_model": "plain resistor of the stated value behind a series switch + select replica (nfet_06v0 4u / 60u, as in the reference leg); no bitline capacitance, no column-mux leakage",
            "program_supply_v": {"value": 5.0, "status": "assumption, held fixed; it only gates the 6 V select devices in this bench"},
            "clock": f"one rising edge at {a.t_edge}, amplitude tracks vdd33; sense_en held asserted",
            "not_simulated": "reference tolerance and comparator offset (spec sense-margin row); no documented source for either; Monte Carlo is a separate issue",
        },
        "measurement_times": {"margin_read": a.t_pre, "decision_read": a.t_out},
        "definitions": {
            "margin_v": "v(sbl) - v(sref) just before the clock edge",
            "signed_margin_v": "margin_v for programmed, -margin_v for intact; positive = correct side of the reference",
            "resolved": "|v(cp) - v(cn)| >= 0.5 * vdd33 after the edge",
            "decision_bit": "1 if v(sense_out) >= 0.7 vdd33, 0 if <= 0.3 vdd33, else null",
        },
        "complete": complete,
        "fuses": fuses,
        "negative_control": {
            "description": f"reference moved from {a.rref:g} to {a.rref_control:g} ohm (inside the intact range); an intact fuse above it must read the wrong side",
            "rref_ohm": a.rref_control,
            "fuse_ohm": sorted(control),
            "flipped_points": flips,
            "demonstrates_bench_can_fail": control_ok,
            "control_points": {rf: sorted(pts, key=key) for rf, (rr, pts) in sorted(control.items())},
        },
        "analog_margin_positive_everywhere": bench_margin_ok,
        "decision_correct_everywhere": bench_decision_ok,
        "verdict": ("data only; see fuses[*].all_margin_positive / all_decisions_ok. "
                    "analog margin positive at every point: %s; comparator decision correct and resolved at every point: %s; "
                    "negative control flips sign: %s" % (bench_margin_ok, bench_decision_ok, control_ok)),
    }
    with open(os.path.join(a.rec, "record.json"), "w") as f:
        json.dump(rec, f, indent=1)
        f.write("\n")
    if not complete:
        print("incomplete: some requests or points have no values (see klt.err, set-report.json)")
        raise SystemExit(3)


if __name__ == "__main__":
    main()
