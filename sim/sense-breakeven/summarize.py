#!/usr/bin/env python3
"""Fold the break-even sweep reports into record.json.

Per corner and per reference (ideal 400 ohm, physical XRref) the raw margin
v(sbl) - v(sref) is read for each swept fuse resistance. The programmed side
(fuse above the reference) is positive; the break-even is the resistance where
the margin crosses zero, found by linear interpolation between the two swept
points that bracket the sign change. A corner whose sweep shows no sign change,
or more than one, has break_even_ohm null and says why: nothing is extrapolated.

The comparator decision measured at --t-out is folded in as well, with the same
decide() as sim/sense-margin. Every swept resistance is read against the
programmed expectation (bit 1), including points below the reference, so
`digital.correct_corners_by_rfuse_ohm` counts the corners that resolved and read
programmed at each resistance, and `lowest_all_corner_rfuse_ohm` is the lowest
swept resistance correct at every corner (null if none). A corner missing from a
sweep point, or with an unusable measurement, is not counted as correct; a valid
wrong-bit reading counts zero and leaves the analog crossing alone.
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import bench_record  # noqa: E402
from sense_decision import decide  # noqa: E402


def finite(x):
    return isinstance(x, (int, float)) and math.isfinite(x)


def crossing(series):
    """series: [(ohm, margin)] sorted by ohm. Returns (ohm|None, reason)."""
    if any(not finite(m) for _, m in series):
        return None, "missing value"
    flips = [(a, b) for a, b in zip(series, series[1:]) if (a[1] < 0) != (b[1] < 0)]
    if len(flips) != 1:
        return None, "%d sign changes in the swept range" % len(flips)
    (r0, m0), (r1, m1) = flips[0]
    return r0 + (r1 - r0) * (0 - m0) / (m1 - m0), "interpolated between %g and %g ohm" % (r0, r1)


PROGRAMMED_BIT = 1  # every swept point is read against "programmed", below the reference too


def corner_key(c):
    return (c["process"], c["temperature_c"], c["supply_v"]["vdd33"])


def fold(reports, stems_by_ohm):
    """stems_by_ohm: {ohm: stem}. Returns per-corner list with margins, decisions and break-even."""
    table, decisions = {}, {}
    for ohm, stem in stems_by_ohm.items():
        for c in reports[stem]["corners"]:
            m = {x["name"]: x.get("value") for x in c.get("measurements", [])}
            sbl, sref = m.get("v_sbl"), m.get("v_sref")
            table.setdefault(corner_key(c), {})[ohm] = (sbl - sref) if finite(sbl) and finite(sref) else None
            res, bit, ok = decide(m.get("v_cp"), m.get("v_cn"), m.get("v_sense_out"),
                                  c["supply_v"]["vdd33"], PROGRAMMED_BIT)
            decisions.setdefault(corner_key(c), {})[ohm] = {
                "resolved": res, "decision_bit": bit, "decision_ok": ok}
    out = []
    for (proc, temp, vdd), pts in sorted(table.items()):
        series = sorted(pts.items())
        be, how = crossing(series)
        out.append({"process": proc, "temp_c": temp, "vdd33_v": vdd,
                    "margin_v_by_rfuse_ohm": {("%g" % o): v for o, v in series},
                    "decision_by_rfuse_ohm": {("%g" % o): d for o, d in sorted(decisions[(proc, temp, vdd)].items())},
                    "break_even_ohm": be, "break_even_basis": how})
    return out


def digital(rows, swept_ohm):
    """Per swept resistance, the distinct corners with a resolved programmed-correct decision."""
    counts = {}
    for o in sorted(swept_ohm):
        counts["%g" % o] = sum(1 for r in rows
                               if r["decision_by_rfuse_ohm"].get("%g" % o, {}).get("decision_ok") is True)
    passing = [o for o in sorted(swept_ohm) if rows and counts["%g" % o] == len(rows)]
    return {"expected_bit": PROGRAMMED_BIT, "corners": len(rows),
            "correct_corners_by_rfuse_ohm": counts,
            "lowest_all_corner_rfuse_ohm": passing[0] if passing else None}


def summary(rows, swept_ohm):
    dig = digital(rows, swept_ohm)
    vals = [r for r in rows if r["break_even_ohm"] is not None]
    if not vals:
        return {"corners": len(rows), "with_break_even": 0, "digital": dig}
    lo = min(vals, key=lambda r: r["break_even_ohm"])
    hi = max(vals, key=lambda r: r["break_even_ohm"])
    pick = lambda r: {k: r[k] for k in ("process", "temp_c", "vdd33_v", "break_even_ohm")}
    return {"corners": len(rows), "with_break_even": len(vals),
            "min_break_even": pick(lo), "max_break_even": pick(hi),
            "spread_ohm": hi["break_even_ohm"] - lo["break_even_ohm"], "digital": dig}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rec")
    ap.add_argument("--rref", type=float, required=True)
    ap.add_argument("--rfuse", required=True)
    ap.add_argument("--t-pre", required=True)
    ap.add_argument("--t-out", required=True)
    ap.add_argument("--t-edge", required=True)
    bench_record.add_common_args(ap)
    a = ap.parse_args()
    ohms = a.rfuse.split()
    if len(ohms) < 2:
        ap.error("--rfuse needs at least two swept values")
    ideal = {float(o): "ideal_rf%s_rr%g" % (o, a.rref) for o in ohms}
    phys = {float(o): "phys_rf%s_rrphys" % o for o in ohms}
    reports = bench_record.load_reports(a.rec, list(ideal.values()) + list(phys.values()))
    process, temp_c, supplies = bench_record.pvt_axes(reports)
    backends, jobs, engines = set(), set(), set()
    for rep in reports.values():
        bench_record.collect_env(rep, backends, jobs, engines)
    ri, rp = fold(reports, ideal), fold(reports, phys)
    complete = all(r["break_even_ohm"] is not None for r in ri + rp)
    rec = {
        **bench_record.header(a, backends, jobs, engines),
        "dut": "efuse_sense (with efuse_comp), extracted from design/efuse_otp_array.spice",
        "pvt": {"process": process, "temp_c": temp_c,
                "vdd33_v": [s["vdd33"] for s in supplies], "source": "decision 0005"},
        "swept_rfuse_ohm": [float(o) for o in ohms],
        "assumptions": {
            "fuse_model": "plain resistor behind a series switch + select replica, as in sim/sense-margin; no bitline capacitance, column-mux leakage, reference tolerance or comparator offset",
            "reference": "ideal: %g ohm (A6, decision 0003); physical: the committed XRref ppolyf_u device" % a.rref,
            "A8_resistor_fs_sf_corner": "fs/sf keep the typical sheet rho (no res_fs/res_sf section in the PDK model library); no documented source",
            "estimate": "break-even is a linear interpolation between the two swept points that bracket the sign change of v(sbl)-v(sref); the sweep step is the interpolation interval",
        },
        "measurement_times": {"margin_read": a.t_pre, "decision_read": a.t_out},
        "definitions": {
            "resolved": "|v(cp) - v(cn)| >= 0.5 * vdd33 after the edge",
            "decision_bit": "1 if v(sense_out) >= 0.7 vdd33, 0 if <= 0.3 vdd33, else null",
            "decision_ok": "true when the comparator resolved and read the programmed bit (1) at the decision sample, including at resistances below the reference",
            "correct_corners_by_rfuse_ohm": "for each swept resistance, the number of distinct corners with decision_ok true for that reference",
            "lowest_all_corner_rfuse_ohm": "the lowest swept resistance at which every corner is correct (decision_ok true), or null if none qualifies",
        },
        "complete": complete,
        "ideal_reference": {"rref_ohm": a.rref, "summary": summary(ri, ideal), "corners": ri},
        "physical_reference": {"summary": summary(rp, phys), "corners": rp},
    }
    bench_record.write_record(a.rec, rec)
    if not complete:
        print("incomplete: some corners have no single sign change in the sweep")
        raise SystemExit(3)


if __name__ == "__main__":
    main()
