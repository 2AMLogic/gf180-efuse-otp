"""Shared record-provenance helpers for the sim/* bench summarizers.

One definition of the provenance fields every bench's record.json carries, so a
change to what run.sh actually checks cannot leave a stale statement behind in
three hand-typed copies. Imported, never run.

`python3 -I` (how run.sh invokes each summarize.py) keeps the script's own
directory off sys.path, so a summarizer imports this with an explicit path
insert:

    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "lib"))
    import bench_record

The three corner benches (program-select, corner-verification, sense-margin)
share all six helpers -- including load_reports(), the refuse-a-partial-set
report-loading step each summarizer used to hand-roll (the guard that has
drifted #146 -> #177 -> #169), and pvt_axes(), which derives a record's `pvt`
grid from the loaded reports so no summarizer keeps a second hand-typed copy
of the decision-0005 grid for run.sh to simulate past (#341) -- and emit a
byte-identical record header.
sim/sense-mc shares only collect_env() and write_record(): its header names
different tool keys (klt_sim_version, klt_yield_pin, no backend).

The simulator version in a record is the one that ran the corners, read from the
reports (`environment.engine_version`), not a probe of whatever simulator the
submitting host happens to carry: these campaigns are batch only, so a local
`ngspice -v` names a binary that executed nothing.
"""
import json
import os
import sys

# The model files pdk_fleet_check() in sim/lib/pdk_env.sh compares between the
# pinned gf180mcuC tree and the gf180mcuD fleet image. VARIANT_SIMULATED below
# is a provenance statement about exactly that check, so it is built from the
# fleet_checked_model_files list in sim/pdk.json — the one list pdk_fleet_check()
# loops: change the check, change the statement.
_pdk_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pdk.json")
with open(_pdk_json) as _f:
    FLEET_CHECKED_MODEL_FILES = tuple(json.load(_f)["fleet_checked_model_files"])
if not FLEET_CHECKED_MODEL_FILES:
    raise SystemExit("bench_record: fleet_checked_model_files in sim/pdk.json is empty")

VARIANT_PINNED = "gf180mcuC"

VARIANT_SIMULATED = (
    "gf180mcuD (fleet image; %s byte-identical to %s, checked by run.sh)"
    % (", ".join(FLEET_CHECKED_MODEL_FILES), VARIANT_PINNED)
)


def add_common_args(ap):
    """Add the provenance arguments every bench summarizer takes from run.sh."""
    ap.add_argument("--pdk-rev", required=True)
    ap.add_argument("--stamp", required=True)
    ap.add_argument("--klt", required=True)
    return ap


def load_reports(rec, stems):
    """Load every expected request's sets/<stem>/report.json, or refuse a partial set.

    stems: the request stems run.sh submitted, named rather than discovered.
    Returns {stem: parsed report}. Two ways a set can be partial, both refused
    with one SystemExit(4) before anything is computed or written:

    absent  the report file is not there (the request errored or was refused,
            bench_submit_set rc=4);
    hollow  the report is present but carries no corners, or fewer than the
            top-level `corner_count` klt itself declared -- it grades nothing
            and would fold the set smaller with no diagnostic. A report with
            no `corner_count` cannot be cross-checked at all and is hollow
            too.

    Both lists accumulate over the whole set, so one refusal shows the
    operator everything wrong with it: the absent block, then the hollow
    block, then the shared `a partial set is not evidence` trailer, then exit
    4 and no record. The wording is operator-facing and shared by all three
    corner benches; "expected reports" is the phrasing that is true of every
    bench's request list ("the grid" is program-select's vocabulary).
    """
    reports, absent, hollow = {}, [], []
    for stem in stems:
        path = os.path.join(rec, "sets", stem, "report.json")
        if not os.path.isfile(path):
            absent.append(stem)
            continue
        with open(path) as f:
            rep = json.load(f)
        n = len(rep.get("corners") or [])
        if not n or rep.get("corner_count") != n:
            hollow.append("%s (corner_count=%r, corners=%d)"
                          % (stem, rep.get("corner_count"), n))
            continue
        reports[stem] = rep
    if absent or hollow:
        if absent:
            print("no report for %d of %d expected requests: %s"
                  % (len(absent), len(stems), " ".join(absent)), file=sys.stderr)
        if hollow:
            print("no usable corners in %d of %d expected reports: %s"
                  % (len(hollow), len(stems), " ".join(hollow)), file=sys.stderr)
        print("a partial set is not evidence; no record written (see %s/set-report.json, "
              "%s/klt.err)" % (rec, rec), file=sys.stderr)
        raise SystemExit(4)
    return reports


def pvt_axes(reports):
    """The (process, temp_c, supplies) PVT axes every report in `reports` ran.

    The record's `pvt` block states the grid the corners actually ran, derived
    from reports[stem]["corners"] (the dict load_reports() returned) rather
    than retyped from decision 0005: if the ratified grid is amended and
    pdk_env.sh re-submits a new one, the record follows the reports instead of
    contradicting the point_list beside it. Processes keep their first-seen
    order in `corners`; temperatures come back sorted; supplies is each
    corner's supply_v dict in first-seen order, so a single-axis grid reads as
    one value per point and a zipped two-axis grid (vdd33 with vprog) keeps
    its pairs. Two reports that ran different grids are not one evidence set:
    like one_submitted() in sim/sense-mc/summarize.py, the disagreement is
    refused with a message naming what each stem ran, never averaged.
    """
    if not reports:
        raise SystemExit("bench_record: no reports to derive a PVT grid from")
    by_stem = {}
    for stem, rep in reports.items():
        process, temps, supplies = [], [], []
        for c in rep["corners"]:
            if c["process"] not in process:
                process.append(c["process"])
            if c["temperature_c"] not in temps:
                temps.append(c["temperature_c"])
            s = c.get("supply_v") or {}
            if s not in supplies:
                supplies.append(s)
        by_stem[stem] = {"process": process, "temp_c": sorted(temps),
                         "supplies": supplies}
    seen = {json.dumps(v, sort_keys=True): s for s, v in by_stem.items()}
    if len(seen) != 1:
        raise SystemExit("bench_record: the reports disagree on the corner grid: "
                         + "; ".join("%s=%s" % (s, k) for k, s in sorted(seen.items())))
    axes = next(iter(by_stem.values()))
    return axes["process"], axes["temp_c"], axes["supplies"]


def collect_env(rep, backends, jobs, engines):
    """Accumulate one klt sim report's backend, remote job ids and engine version.

    backends: set of json.dumps(backend, sort_keys=True) strings, or None for a
              bench whose record has no `backend` key (sim/sense-mc).
    jobs:     set of remote job id strings; both the single `job_id` and the
              `job_ids` list form are read, and a missing one adds nothing.
    engines:  set of `environment.engine_version` strings -- the simulator that
              ran this report's corners. A report without one adds nothing, so
              an empty set reads as an empty list rather than a guessed version.

    Returns the report, so a caller can load and collect in one expression.
    """
    env = rep.get("environment", {})
    if backends is not None:
        backends.add(json.dumps(env.get("backend", {}), sort_keys=True))
    remote = env.get("remote") or {}
    for k in ("job_id", "job_ids"):
        v = remote.get(k)
        if v:
            jobs.update(v if isinstance(v, list) else [v])
    engine_version = env.get("engine_version")
    if engine_version:
        engines.add(str(engine_version))
    return rep


def header(a, backends, jobs, engines):
    """The provenance header of a corner bench's record.json, in record order.

    `a` is the parsed namespace holding the add_common_args() values. `engines`
    is the collect_env() set of engine versions; it is emitted sorted, so a set
    whose corners ran on more than one simulator version stays visible instead
    of collapsing to one value.
    """
    return {
        "pdk_revision": a.pdk_rev,
        "variant_pinned": VARIANT_PINNED,
        "variant_simulated": VARIANT_SIMULATED,
        "timestamp_utc": a.stamp,
        "engine_versions": sorted(engines),
        "klt_version": a.klt,
        "backend": [json.loads(b) for b in sorted(backends)],
        "remote_job_ids": sorted(jobs),
    }


def write_record(rec_dir, rec):
    """Write rec as <rec_dir>/record.json in the benches' committed format."""
    with open(os.path.join(rec_dir, "record.json"), "w") as f:
        json.dump(rec, f, indent=1)
        f.write("\n")
