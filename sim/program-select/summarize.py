#!/usr/bin/env python3
"""Fold the per-(fuse, width) klt sim reports of a program-select run into record.json.

Called by run.sh with the record directory and the grid it submitted
(--fuse-ohms, --widths-um). Loads sets/cell_r<ohm>_w<um>/report.json for every
expected (fuse, width) pair by name, so a request whose report never came back
is a hard error rather than a smaller grid. Lists every PVT point and names the
binding corner (minimum fuse current) per width. A width is `all_pass` only
when every point carries a finite current >= the requirement; `candidate`
additionally needs every Vgs/Vds within the stated voltage limit. No width is
chosen unless a candidate exists.
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import bench_record  # noqa: E402  (needs the path insert above under python3 -I)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rec")
    ap.add_argument("--ireq", type=float, required=True)
    ap.add_argument("--vmax", type=float, required=True)
    ap.add_argument("--rroute", type=float, required=True)
    ap.add_argument("--fuse-ohms", required=True)
    ap.add_argument("--widths-um", required=True)
    bench_record.add_common_args(ap)
    a = ap.parse_args()
    fuse_ohms = [int(x) for x in a.fuse_ohms.split()]
    widths_um = [int(x) for x in a.widths_um.split()]
    if not fuse_ohms or not widths_um:
        # An empty grid would make every verdict below vacuously true.
        ap.error("--fuse-ohms and --widths-um must each name at least one value")

    # The grid run.sh submitted, named rather than discovered. A partial set (a
    # request errored or was refused, bench_submit_set rc=4) is not evidence, so
    # refuse before anything is computed or written -- the same rule
    # sim/sense-mc/run.sh applies to its own set.
    expected = [(r, w, "cell_r%d_w%d" % (r, w)) for r in fuse_ohms for w in widths_um]
    missing = [stem for _, _, stem in expected
               if not os.path.isfile(os.path.join(a.rec, "sets", stem, "report.json"))]
    if missing:
        print("no report for %d of %d expected requests: %s"
              % (len(missing), len(expected), " ".join(missing)), file=sys.stderr)
        print("a partial set is not evidence; no record written (see %s/set-report.json, "
              "%s/klt.err)" % (a.rec, a.rec), file=sys.stderr)
        raise SystemExit(4)

    widths = {}
    backends, jobs, engines = set(), set(), set()
    for fuse, wum, stem in expected:
        path = os.path.join(a.rec, "sets", stem, "report.json")
        rep = bench_record.collect_env(json.load(open(path)), backends, jobs, engines)
        for c in rep["corners"]:
            m = {x["name"]: x.get("value") for x in c.get("measurements", [])}
            i, vgs, vds = m.get("i_fuse"), m.get("vgs"), m.get("vds")
            ok = (c.get("status") in ("pass", "fail") and i is not None
                  and math.isfinite(i))
            pt = {
                "process": c["process"],
                "temp_c": c["temperature_c"],
                "vprog_v": c["supply_v"]["vdd"],
                "fuse_ohm": fuse,
                "i_fuse_a": i,
                "vgs_v": vgs,
                "vds_v": vds,
                "status": c.get("status"),
                "pass": bool(ok and i >= a.ireq),
            }
            widths.setdefault(wum * 1e-6, []).append(pt)

    out_w = []
    for w in sorted(widths):
        pts = sorted(widths[w], key=lambda p: (p["fuse_ohm"], p["process"],
                                               p["temp_c"], p["vprog_v"]))
        valid = [p for p in pts if p["i_fuse_a"] is not None and math.isfinite(p["i_fuse_a"])]
        bind = min(valid, key=lambda p: p["i_fuse_a"]) if valid else None
        all_pass = bool(pts) and all(p["pass"] for p in pts)
        vmax = max((max(p["vgs_v"], p["vds_v"]) for p in valid
                    if p["vgs_v"] is not None and p["vds_v"] is not None), default=None)
        out_w.append({
            "w_um": round(w * 1e6, 6),
            "points": len(pts),
            "all_pass": all_pass,
            "failing_points": [p for p in pts if not p["pass"]],
            "min_i_fuse_a": bind["i_fuse_a"] if bind else None,
            "binding_corner": bind,
            "max_vgs_vds_v": vmax,
            "within_voltage_limit": vmax is not None and vmax <= a.vmax,
            "candidate": all_pass and vmax is not None and vmax <= a.vmax,
            "point_list": pts,
        })
    complete = all(p["i_fuse_a"] is not None and math.isfinite(p["i_fuse_a"])
                   for w in out_w for p in w["point_list"])
    cands = [w for w in out_w if w["candidate"]]
    chosen = cands[0]["w_um"] if cands else None

    rec = {
        **bench_record.header(a, backends, jobs, engines),
        "device": "nfet_06v0, L=0.7u, nf=1",
        "pvt": {"process": ["typical", "ff", "ss", "fs", "sf"],
                "temp_c": [-40, 25, 125], "vprog_v": [4.5, 5.0, 5.5],
                "fuse_ohm": fuse_ohms},
        "requirement": {"i_fuse_min_a": a.ireq, "source": "assumption A2, spec/efuse-otp.md section 2 (no PDK source)"},
        "assumptions": {
            "routing_resistance_ohm": {"value": a.rroute, "status": "assumption, no documented source"},
            "gate_drive": {"value": "ideal source equal to the program supply at the corner (Vgs = Vprog)", "status": "assumption, no documented source"},
            "fuse_140_260_ohm": "plain resistor; the PDK efuse subcircuit (rfuse = 200*(1-pblow)+900*pblow) cannot reach 140 or 260 ohm. 200 ohm uses the PDK efuse subcircuit with pblow=0.",
            "fuse_range": "A4 140-260 ohm; only 200 ohm is documented",
            "voltage_limit_v": {"value": a.vmax, "status": "assumption, no documented rating: searched sm141064.ngspice, gf180mcu-pdk.readthedocs.io analog/spice/elec_specs_2 (2.0 Medium Voltage Devices (6V)) and elec_specs_7_5, and IPs/IO/gf180mcu_fd_io/conditions (checked 2026-10-23); none gives a Vgs/Vds/Vgd limit. 6.0 V is the device-class label and the Idsat test bias, not a rating. Vgs and Vds are recorded per point so a different limit can be applied."},
        },
        "complete": complete,
        "widths": out_w,
        "chosen_w_um": chosen,
        "verdict": ("smallest candidate width: every point passes and Vgs/Vds are within the assumed limit"
                    if chosen is not None else
                    "no width chosen: no swept width passes every point within the assumed limit"),
    }
    bench_record.write_record(a.rec, rec)
    if not complete:
        print("incomplete: some points have no current "
              "(see sets/cell_r<ohm>_w<um>/report.json diagnostics)")
        raise SystemExit(3)


if __name__ == "__main__":
    main()
