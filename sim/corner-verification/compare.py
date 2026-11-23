#!/usr/bin/env python3
"""Per-corner comparison of two corner-verification records (issue #309).

  python3 -I compare.py <new record dir> <baseline record dir>

Writes <new record dir>/comparison.json: for every process x temperature x
supply pair x fuse value, the new and baseline delivered current and their
difference, plus the DC level-shifter checks at each selected-cell point (all
three measurements finite; word-line voltage equal to that corner's vprog to the
nearest mV; loaded bit-line voltage above that corner's vdd33; i_fuse at least
the requirement). Exit 0 always: pass/fail is data, graded from the file.
"""
import json, math, sys
from pathlib import Path

IREQ = 0.010
FUSES = (140, 200, 260)


def points(rec):
    out = {}
    for r in FUSES:
        rep = json.loads((rec / "sets" / f"prog_rf{r}" / "report.json").read_text())
        for c in rep["corners"]:
            m = {x["name"]: x["value"] for x in c["measurements"]}
            key = (c["process"], c["temperature_c"], c["supply_v"]["vdd33"], c["supply_v"]["vprog"], r)
            out[key] = m
    return out


def main(new_dir, base_dir):
    new_dir, base_dir = Path(new_dir), Path(base_dir)
    new, base = points(new_dir), points(base_dir)
    rows, exc = [], []
    for k in sorted(new):
        proc, t, v33, vp, r = k
        n, b = new[k], base.get(k)
        finite = all(isinstance(n.get(x), (int, float)) and math.isfinite(n[x])
                     for x in ("i_fuse", "v_wl", "v_bl", "v_sel_d"))
        wl_ok = finite and round(n["v_wl"], 3) == round(vp, 3)
        bl_ok = finite and n["v_bl"] > v33
        i_ok = finite and n["i_fuse"] >= IREQ
        row = {"process": proc, "temp_c": t, "vdd33_v": v33, "vprog_v": vp, "fuse_ohm": r,
               "i_new_a": n.get("i_fuse"), "i_base_a": b and b.get("i_fuse"),
               "i_delta_a": (n["i_fuse"] - b["i_fuse"]) if finite and b else None,
               "v_wl_err_v": abs(n["v_wl"] - vp) if finite else None,
               "v_bl_margin_v": (n["v_bl"] - v33) if finite else None,
               "finite": finite, "wl_ok": wl_ok, "bl_ok": bl_ok, "i_ok": i_ok}
        rows.append(row)
        if not (finite and wl_ok and bl_ok and i_ok):
            exc.append(row)
    d = [x["i_delta_a"] for x in rows if x["i_delta_a"] is not None]
    summ = {"points": len(rows), "baseline_points_matched": len(d), "exceptions": len(exc),
            "min_i_new_a": min(x["i_new_a"] for x in rows),
            "min_i_base_a": min(x["i_base_a"] for x in rows if x["i_base_a"] is not None),
            "i_delta_a_min": min(d), "i_delta_a_max": max(d),
            "max_wl_err_v": max(x["v_wl_err_v"] for x in rows),
            "min_bl_margin_v": min(x["v_bl_margin_v"] for x in rows)}
    (new_dir / "comparison.json").write_text(json.dumps(
        {"baseline": base_dir.name, "ireq_a": IREQ, "summary": summ, "exceptions": exc, "points": rows},
        indent=1) + "\n")
    print(json.dumps(summ, indent=1))


main(*sys.argv[1:3])
