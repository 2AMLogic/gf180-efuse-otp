#!/usr/bin/env python3
"""Fold a sense-mc run into record.json.

Called by run.sh with the record directory. Reads <stem>.json (the six requests run.sh
submitted -- two ideal-reference nominals, two physical-XRref nominals, two negative
controls -- for the corner grid and the graded decision limit), sets/<stem>/report.json
(the klt sim Monte Carlo reports) and yield/<pop>[_phys].yield.json (the cited klt yield
report, margin_v only) and yield/<pop>[_phys].decision.yield.json (the uncited
decision_margin report). Pass/fail is data in the record, not an exit status.

Run constants are never retyped here: run.sh either passes one (--rref, --rfuse-intact, ...)
or wrote it into the requests this reads back, so the record states the value the grid was
actually submitted and graded under.

--physical-reference summarizes the physical-XRref requests (stems *_rrphys, yields
<pop>_phys) under `physical_reference`; without it the record carries only the ideal
populations, so records predating the physical variant regenerate unchanged.
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


def stem(prefix, rfuse, rref):
    """The request stem run.sh builds for one population / reference pair."""
    return f"{prefix}_rf{rfuse:g}_rr{rref:g}"


def phys_stem(prefix, rfuse):
    """The request stem of one population's physical-XRref nominal (run.sh's `phys` mode)."""
    return f"{prefix}_rf{rfuse:g}_rrphys"


def one_submitted(by_stem, what):
    """The value all submitted requests agree on; a disagreement is not summarizable."""
    seen = {json.dumps(v, sort_keys=True): s for s, v in by_stem.items()}
    if len(seen) != 1:
        raise SystemExit(f"summarize.py: the requests disagree on the {what}: "
                         + "; ".join(f"{s}={k}" for k, s in sorted(seen.items())))
    return next(iter(by_stem.values()))


def limit_min(req, name):
    """The lower limit a request declares for one measurement, i.e. what klt graded it at."""
    m = next(x for x in req["measurements"] if x["name"] == name)
    return m["limits"]["min"]


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
    for a in ("pdk-rev", "stamp", "klt", "klt-pin"):
        ap.add_argument("--" + a, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--n-nominal", type=int, required=True)
    ap.add_argument("--n-control", type=int, required=True)
    ap.add_argument("--sigma-rref", type=float, required=True)
    ap.add_argument("--mismatch-scale", type=float, required=True)
    ap.add_argument("--rref", type=float, required=True)
    ap.add_argument("--rfuse-intact", type=int, required=True)
    ap.add_argument("--rfuse-prog", type=int, required=True)
    ap.add_argument("--rref-ctl-intact", type=int, required=True)
    ap.add_argument("--rref-ctl-prog", type=int, required=True)
    ap.add_argument("--min-samples", type=int, required=True)
    ap.add_argument("--ci-halfwidth", type=float, required=True)
    ap.add_argument("--physical-reference", action="store_true",
                    help="also read the two physical-XRref nominals (*_rrphys, yields "
                         "<pop>_phys): the committed ppolyf_u reference with the injected "
                         "tolerance on its series multiplier s, summarized under "
                         "physical_reference")
    a = ap.parse_args()

    pops = {
        "intact": {"nominal": stem("mc_intact", a.rfuse_intact, a.rref),
                   "control": stem("ctl_intact", a.rfuse_intact, a.rref_ctl_intact),
                   "phys": phys_stem("mc_intact", a.rfuse_intact),
                   "rfuse_ohm": a.rfuse_intact, "bound": "A4 upper edge"},
        "programmed": {"nominal": stem("mc_prog", a.rfuse_prog, a.rref),
                       "control": stem("ctl_prog", a.rfuse_prog, a.rref_ctl_prog),
                       "phys": phys_stem("mc_prog", a.rfuse_prog),
                       "rfuse_ohm": a.rfuse_prog, "bound": "A5 lower edge"},
    }

    # What the grid was actually submitted and graded under, read back from the requests
    # run.sh wrote into this record rather than retyped: the corner grid and the
    # decision_margin lower limit. The physical-reference nominals join the consistency
    # check when they are part of the set.
    roles = ("nominal", "control") + (("phys",) if a.physical_reference else ())
    reqs = {d[role]: jl(os.path.join(a.rec, d[role] + ".json"))
            for d in pops.values() for role in roles}
    grid = one_submitted({k: v["corners"] for k, v in reqs.items()}, "corner grid")
    dmin = one_submitted({k: limit_min(v, "decision_margin") for k, v in reqs.items()},
                         "decision_margin lower limit")
    process = [p["name"] for p in grid["process"]]
    temps, vdd = grid["temperature_c"], grid["supply_v"]["vdd33"]
    n_corners = len(process) * len(temps) * len(vdd)
    # run.sh grades decision_margin as the distance of sense_out/vdd33 from the 0.5 midpoint
    # (its `dec` expressions), so the pass rails are that midpoint plus/minus the limit.
    midpoint = 0.5

    def population(d, nominal, yield_name, reference):
        """One nominal/control pair: per-set stats from the two reports, graded yields."""
        sets = {}
        for role, s in (("nominal", nominal), ("control", d["control"])):
            rep = bench_record.collect_env(
                jl(os.path.join(a.rec, "sets", s, "report.json")), None, jobs, engines)
            sets[role] = {"stem": s, "corner_count": rep["corner_count"], "errored": rep["errored"],
                          "stats": set_stats(rep)}
        y = os.path.join(a.rec, "yield", yield_name)
        return {
            "rfuse_ohm": d["rfuse_ohm"], "why_this_value": d["bound"],
            "rref_nominal_ohm": a.rref, "reference": reference, "sets": sets,
            "cited_yield_report": f"yield/{yield_name}.yield.json",
            "cited": graded(y + ".yield.json"),
            "uncited_decision_report": f"yield/{yield_name}.decision.yield.json",
            "decision": graded(y + ".decision.yield.json"),
        }

    ypop = {"intact": "intact", "programmed": "prog"}
    ideal_reference = ("ideal R stand-in at 400 ohm carrying the injected multiplier "
                       "(mc_inj_rref_r); value-parametric by design")
    physical_reference = ("committed XRref (ppolyf_u, 0.8 um x 1.05 um, 400.386 ohm at 25 C "
                          "typical) with the injected tolerance on its series multiplier s "
                          "(mc_inj_xrref_s), scaling terminal and body resistance together")
    jobs, engines, out_pops, out_phys = set(), set(), {}, {}
    for pop, d in pops.items():
        out_pops[pop] = population(d, d["nominal"], ypop[pop], ideal_reference)
        if a.physical_reference:
            out_phys[pop] = population(d, d["phys"], ypop[pop] + "_phys", physical_reference)

    def discipline(populations):
        return all(
            "error" not in p["cited"]
            and all(m["sample_size_verdict"] == "sufficient" and m["negative_control_verdict"] == "detected"
                    for m in p["cited"]["measurements"])
            for p in populations.values())

    cited_ok = discipline(out_pops)
    finding_pops = {}
    for pop, p in out_pops.items():
        finding_pops[pop] = p
        if a.physical_reference:
            finding_pops[pop + " (physical XRref)"] = out_phys[pop]
    rec = {
        "pdk_revision": a.pdk_rev, "variant_pinned": bench_record.VARIANT_PINNED,
        "variant_simulated": bench_record.VARIANT_SIMULATED,
        "timestamp_utc": a.stamp, "engine_versions": sorted(engines), "klt_sim_version": a.klt,
        "klt_yield_pin": a.klt_pin, "remote_job_ids": sorted(jobs),
        "tool_versions": {"klt_sim": a.klt, "klt_yield": a.klt_pin},
        "dut": "efuse_sense (with efuse_comp), extracted from design/efuse_otp_array.spice",
        "corners": f"{n_corners} per request: {len(process)} process x {len(temps)} temperature"
                   f" x {len(vdd)} vdd33 (decision 0005); see pvt",
        "pvt": {"process": process, "temp_c": temps,
                "vdd33_v": vdd, "source": "decision 0005",
                "note": f"every sample is drawn at every one of the {n_corners} corners: MC is combined with, not instead of, the corner grid"},
        "monte_carlo": {
            "seed": a.seed, "seed_scope": "point", "vary": "mismatch",
            "n_per_corner_nominal": a.n_nominal, "n_per_corner_control": a.n_control,
            "samples_per_nominal_request": a.n_nominal * n_corners,
            "samples_per_control_request": a.n_control * n_corners,
            "mismatch": f"PDK MOS mismatch at its model default (sw_stat_mismatch={a.mismatch_scale:g}); covers comparator pair, mirror and bias devices",
            "reference_tolerance": (
                f"klt-injected Gaussian multiplier on Rref, relative sigma {a.sigma_rref:g}"
                + ("; the physical-reference requests inject the same relative sigma on the committed "
                   "XRref's series multiplier s, scaling terminal and body resistance together"
                   if a.physical_reference else "")),
            "reproducibility": "the draws are a pure function of seed, seed_scope=point and the corner identity; re-running run.sh with the same constants reproduces the sample sequence",
        },
        "assumptions": {
            "A4_intact_ohm": f"140-260; only the 200 ohm point is documented. {a.rfuse_intact:g} (upper edge) is the binding intact value here",
            "A5_programmed_ohm": f">=630 up to open; only the 900 ohm point is documented. {a.rfuse_prog:g} (lower edge) is the binding programmed value here",
            "A6_reference_ohm": f"{a.rref:g} (decision 0003)",
            "A7_reference_relative_sigma": f"{a.sigma_rref:g}: NO documented source for the reference tolerance; a stated working value, not a fact (new assumption, not in spec/efuse-otp.md)",
            "A8_resistor_fs_sf_corner": "the PDK model library declares resistor sections res_typical/res_ss/res_ff and no res_fs/res_sf, so the fs and sf corners keep the typical sheet rho; this has no documented source (new assumption, not in spec/efuse-otp.md); two of the five process corners therefore do not exercise the resistor corner dependence",
            "fuse_model": "plain resistor behind a series switch + select replica; the fuse value is not varied inside the Monte Carlo (the A4/A5 range edges are the evaluated points)",
            "not_covered": "bitline capacitance, column-mux leakage, supply noise, post-layout parasitics",
        },
        "limits": {
            "margin_v": "> 0 V (spec/efuse-otp.md section 2, Sense margin: positive over the A4/A5 ranges); signed so that positive is the correct side of the reference",
            "decision_margin": f">= {dmin:g} (sense_out/vdd33 at least {dmin:g} past the {midpoint:g} midpoint,"
                               f" signed for the expected bit); same {midpoint + dmin:g} / {midpoint - dmin:g}"
                               f" rails as sim/sense-margin",
        },
        "min_samples": a.min_samples, "target_ci_halfwidth": a.ci_halfwidth, "confidence": 0.95,
        "populations": out_pops,
        "cited_evidence_meets_item6_discipline": cited_ok,
        "decision_path_finding": decision_finding(finding_pops),
    }
    if a.physical_reference:
        rec["physical_reference"] = {
            "description": ("the same two nominal populations against the committed XRref (ppolyf_u "
                            "device, including its terminal resistance and its corner dependence; "
                            "fs/sf keep the typical sheet rho, A8) instead of the ideal stand-in; "
                            "the injected tolerance multiplies its series parameter s, so terminal "
                            "and body resistance vary together. Paired with the same value-skewed "
                            "negative controls as the ideal populations"),
            "populations": out_phys,
            "cited_evidence_meets_item6_discipline": discipline(out_phys),
        }
    bench_record.write_record(a.rec, rec)


if __name__ == "__main__":
    main()
