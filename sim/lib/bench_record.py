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
share all four helpers and emit a byte-identical record header. sim/sense-mc
shares only collect_env() and write_record(): its header names different tool
keys (klt_sim_version, klt_yield_pin, no backend).

The simulator version in a record is the one that ran the corners, read from the
reports (`environment.engine_version`), not a probe of whatever simulator the
submitting host happens to carry: these campaigns are batch only, so a local
`ngspice -v` names a binary that executed nothing.
"""
import json
import os

# The model files pdk_fleet_check() in sim/lib/pdk_env.sh compares between the
# pinned gf180mcuC tree and the gf180mcuD fleet image. VARIANT_SIMULATED below
# is a provenance statement about exactly that check, so it is built from this
# list rather than restating it: change the check, change the statement.
FLEET_CHECKED_MODEL_FILES = ("sm141064.ngspice", "sm141064.spice", "design.ngspice")

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
