#!/usr/bin/env python3
"""Fold the per-(fuse, width) klt sim reports of a program-select run into record.json.

Called by run.sh with the record directory. Reads sets/cell_r<ohm>_w<um>/report.json,
lists every PVT point per width, and names the binding corner
(minimum fuse current) per width. A width is `all_pass` only when every point
carries a finite current >= the requirement; `candidate` additionally needs
every Vgs/Vds within the stated voltage limit. No width is chosen unless a
candidate exists.
"""
import argparse
import glob
import json
import math
import os
import re


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rec")
    ap.add_argument("--ireq", type=float, required=True)
    ap.add_argument("--vmax", type=float, required=True)
    ap.add_argument("--rroute", type=float, required=True)
    ap.add_argument("--pdk-rev", required=True)
    ap.add_argument("--stamp", required=True)
    ap.add_argument("--ngspice", required=True)
    ap.add_argument("--klt", required=True)
    a = ap.parse_args()

    widths = {}
    backends, jobs = set(), set()
    expected_per_width = None
    for path in sorted(glob.glob(os.path.join(a.rec, "sets", "cell_r*_w*", "report.json"))):
        m_ = re.search(r"cell_r(\d+)_w(\d+)", path)
        fuse, wum = int(m_.group(1)), int(m_.group(2))
        rep = json.load(open(path))
        env = rep.get("environment", {})
        backends.add(json.dumps(env.get("backend", {}), sort_keys=True))
        remote = env.get("remote") or {}
        for k in ("job_id", "job_ids"):
            v = remote.get(k)
            if v:
                jobs.update(v if isinstance(v, list) else [v])
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
        "pdk_revision": a.pdk_rev,
        "variant_pinned": "gf180mcuC",
        "variant_simulated": "gf180mcuD (fleet image; sm141064.ngspice, sm141064.spice, design.ngspice byte-identical to gf180mcuC, checked by run.sh)",
        "timestamp_utc": a.stamp,
        "ngspice_version_local": a.ngspice,
        "klt_version": a.klt,
        "backend": [json.loads(b) for b in sorted(backends)],
        "remote_job_ids": sorted(jobs),
        "device": "nfet_06v0, L=0.7u, nf=1",
        "pvt": {"process": ["typical", "ff", "ss", "fs", "sf"],
                "temp_c": [-40, 25, 125], "vprog_v": [4.5, 5.0, 5.5],
                "fuse_ohm": [140, 200, 260]},
        "requirement": {"i_fuse_min_a": a.ireq, "source": "assumption A2, spec/efuse-otp.md section 2 (no PDK source)"},
        "assumptions": {
            "routing_resistance_ohm": {"value": a.rroute, "status": "assumption, no documented source"},
            "gate_drive": {"value": "ideal source equal to the program supply at the corner (Vgs = Vprog)", "status": "assumption, no documented source"},
            "fuse_140_260_ohm": "plain resistor; the PDK efuse subcircuit (rfuse = 200*(1-pblow)+900*pblow) cannot reach 140 or 260 ohm. 200 ohm uses the PDK efuse subcircuit with pblow=0.",
            "fuse_range": "A4 140-260 ohm; only 200 ohm is documented",
            "voltage_limit_v": {"value": a.vmax, "status": "assumption: sm141064.ngspice labels nfet_06v0 as the 6.0V NMOS; no numeric rating found in the model file or spec/. Vgs and Vds are recorded per point so a different limit can be applied."},
        },
        "complete": complete,
        "widths": out_w,
        "chosen_w_um": chosen,
        "verdict": ("smallest candidate width: every point passes and Vgs/Vds are within the assumed limit"
                    if chosen is not None else
                    "no width chosen: no swept width passes every point within the assumed limit"),
    }
    with open(os.path.join(a.rec, "record.json"), "w") as f:
        json.dump(rec, f, indent=1)
        f.write("\n")
    if not complete:
        print("incomplete: some points have no current (see report_r*.json diagnostics)")
        raise SystemExit(3)


if __name__ == "__main__":
    main()
