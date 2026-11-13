#!/usr/bin/env python3
"""Fold a sense-mc run into record.json.

Called by run.sh with the record directory. Reads sets/<stem>/report.json (the four klt sim
Monte Carlo reports) and yield/<pop>.yield.json (the cited klt yield report, margin_v only)
and yield/<pop>.decision.yield.json (the uncited decision_margin report). Pass/fail is data
in the record, not an exit status.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import bench_record  # noqa: E402  (needs the path insert above under python3 -I)


def jl(path):
    with open(path) as f:
        return json.load(f)


def corner_key(c):
    return f"{c['process']}/{c['temperature_c']}C/{c['supply_v']['vdd33']:.2f}V"


def set_stats(rep):
    """Per-measurement sample stats and the binding (minimum-margin) corner of one MC report."""
    out = {}
    for name in ("margin_v", "decision_margin"):
        vals = []
        per_corner = collections.defaultdict(lambda: {"n": 0, "fail": 0, "min": None})
        for c in rep["corners"]:
            m = next((x for x in c.get("measurements", []) if x["name"] == name), None)
            if not m or m.get("value") is None:
                continue
            k = corner_key(c)
            pc = per_corner[k]
            pc["n"] += 1
            pc["fail"] += m.get("status") != "pass"
            pc["min"] = m["value"] if pc["min"] is None else min(pc["min"], m["value"])
            vals.append(m["value"])
        worst = min(per_corner.items(), key=lambda kv: kv[1]["min"]) if per_corner else None
        out[name] = {
            "samples": len(vals),
            "min": min(vals) if vals else None,
            "max": max(vals) if vals else None,
            "failing_samples": sum(v["fail"] for v in per_corner.values()),
            "corners_with_a_failing_sample": sum(1 for v in per_corner.values() if v["fail"]),
            "corners": len(per_corner),
            "binding_corner": {"corner": worst[0], **worst[1]} if worst else None,
        }
    return out


def graded(path):
    rep = jl(path)
    if "error" in rep:
        return {"error": rep["error"]}
    rows = []
    for m in rep["measurements"]:
        nc = m.get("negative_control") or {}
        emp = m["yield"]["empirical"]
        rows.append({
            "name": m["name"],
            "n": emp["n"],
            "yield_empirical": emp["estimate"],
            "yield_ci95": [emp["confidence_interval"]["low"], emp["confidence_interval"]["high"]],
            "sample_size_verdict": m["sample_size"]["verdict"],
            "required_n": m["sample_size"].get("required_n"),
            "negative_control_verdict": nc.get("verdict", "not_declared"),
            "negative_control_yield": (nc.get("yield") or {}).get("empirical", {}).get("estimate"),
        })
    return {"status": rep.get("status"), "measurements": rows}


def decision_finding(pops):
    """Describe the uncited decision_margin grading from the graded data (no fixed text)."""
    parts = []
    for name, p in pops.items():
        ms = p["decision"].get("measurements") or []
        if not ms:
            parts.append(f"{name}: decision_margin not graded")
            continue
        m = ms[0]
        parts.append(f"{name}: decision yield {m['yield_empirical']:.4f} over {m['n']} samples "
                     f"(sample size {m['sample_size_verdict']}, negative control {m['negative_control_verdict']})")
    return ("decision_margin (latched sense_out past the midpoint) is reported, not cited: "
            + "; ".join(parts) + ". A decision yield below 1.0 is comparator offset plus reference tolerance "
            "flipping or failing to resolve the latched bit; read the per-corner stats in populations.*.sets.nominal.stats.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rec")
    for a in ("pdk-rev", "stamp", "ngspice", "klt", "klt-pin"):
        ap.add_argument("--" + a, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--n-nominal", type=int, required=True)
    ap.add_argument("--n-control", type=int, required=True)
    ap.add_argument("--sigma-rref", type=float, required=True)
    ap.add_argument("--mismatch-scale", type=float, required=True)
    ap.add_argument("--rref", type=float, required=True)
    ap.add_argument("--min-samples", type=int, required=True)
    ap.add_argument("--ci-halfwidth", type=float, required=True)
    a = ap.parse_args()

    pops = {
        "intact": {"nominal": "mc_intact_rf260_rr400", "control": "ctl_intact_rf260_rr200", "rfuse_ohm": 260, "bound": "A4 upper edge"},
        "programmed": {"nominal": "mc_prog_rf630_rr400", "control": "ctl_prog_rf630_rr1000", "rfuse_ohm": 630, "bound": "A5 lower edge"},
    }
    ypop = {"intact": "intact", "programmed": "prog"}
    jobs, out_pops = set(), {}
    for pop, d in pops.items():
        sets = {}
        for role in ("nominal", "control"):
            rep = bench_record.collect_env(
                jl(os.path.join(a.rec, "sets", d[role], "report.json")), None, jobs)
            sets[role] = {"stem": d[role], "corner_count": rep["corner_count"], "errored": rep["errored"],
                          "stats": set_stats(rep)}
        y = os.path.join(a.rec, "yield", ypop[pop])
        out_pops[pop] = {
            "rfuse_ohm": d["rfuse_ohm"], "why_this_value": d["bound"],
            "rref_nominal_ohm": a.rref, "sets": sets,
            "cited_yield_report": f"yield/{ypop[pop]}.yield.json",
            "cited": graded(y + ".yield.json"),
            "uncited_decision_report": f"yield/{ypop[pop]}.decision.yield.json",
            "decision": graded(y + ".decision.yield.json"),
        }

    cited_ok = all(
        "error" not in p["cited"]
        and all(m["sample_size_verdict"] == "sufficient" and m["negative_control_verdict"] == "detected"
                for m in p["cited"]["measurements"])
        for p in out_pops.values())
    rec = {
        "pdk_revision": a.pdk_rev, "variant_pinned": bench_record.VARIANT_PINNED,
        "variant_simulated": bench_record.VARIANT_SIMULATED,
        "timestamp_utc": a.stamp, "ngspice_version_local": a.ngspice, "klt_sim_version": a.klt,
        "klt_yield_pin": a.klt_pin, "remote_job_ids": sorted(jobs),
        "tool_versions": {"ngspice_local": a.ngspice, "klt_sim": a.klt, "klt_yield": a.klt_pin},
        "dut": "efuse_sense (with efuse_comp), extracted from design/efuse_otp_array.spice",
        "corners": "45 per request: 5 process x 3 temperature x 3 vdd33 (decision 0005); see pvt",
        "pvt": {"process": ["typical", "ff", "ss", "fs", "sf"], "temp_c": [-40, 25, 125],
                "vdd33_v": [2.97, 3.30, 3.63], "source": "decision 0005",
                "note": "every sample is drawn at every one of the 45 corners: MC is combined with, not instead of, the corner grid"},
        "monte_carlo": {
            "seed": a.seed, "seed_scope": "point", "vary": "mismatch",
            "n_per_corner_nominal": a.n_nominal, "n_per_corner_control": a.n_control,
            "samples_per_nominal_request": a.n_nominal * 45, "samples_per_control_request": a.n_control * 45,
            "mismatch": f"PDK MOS mismatch at its model default (sw_stat_mismatch={a.mismatch_scale:g}); covers comparator pair, mirror and bias devices",
            "reference_tolerance": f"klt-injected Gaussian multiplier on Rref, relative sigma {a.sigma_rref:g}",
            "reproducibility": "the draws are a pure function of seed, seed_scope=point and the corner identity; re-running run.sh with the same constants reproduces the sample sequence",
        },
        "assumptions": {
            "A4_intact_ohm": "140-260; only the 200 ohm point is documented. 260 (upper edge) is the binding intact value here",
            "A5_programmed_ohm": ">=630 up to open; only the 900 ohm point is documented. 630 (lower edge) is the binding programmed value here",
            "A6_reference_ohm": "400 (decision 0003)",
            "A7_reference_relative_sigma": f"{a.sigma_rref:g}: NO documented source for the reference tolerance; a stated working value, not a fact (new assumption, not in spec/efuse-otp.md)",
            "fuse_model": "plain resistor behind a series switch + select replica; the fuse value is not varied inside the Monte Carlo (the A4/A5 range edges are the evaluated points)",
            "not_covered": "bitline capacitance, column-mux leakage, supply noise, post-layout parasitics",
        },
        "limits": {
            "margin_v": "> 0 V (spec/efuse-otp.md section 2, Sense margin: positive over the A4/A5 ranges); signed so that positive is the correct side of the reference",
            "decision_margin": f">= 0.2 (sense_out/vdd33 at least 0.2 past the 0.5 midpoint, signed for the expected bit); same 0.7 / 0.3 rails as sim/sense-margin",
        },
        "min_samples": a.min_samples, "target_ci_halfwidth": a.ci_halfwidth, "confidence": 0.95,
        "populations": out_pops,
        "cited_evidence_meets_item6_discipline": cited_ok,
        "decision_path_finding": decision_finding(out_pops),
    }
    bench_record.write_record(a.rec, rec)


if __name__ == "__main__":
    main()
