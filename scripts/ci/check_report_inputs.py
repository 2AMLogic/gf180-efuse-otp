#!/usr/bin/env python3
"""Check that each gated layout report still describes the stream beside it
(stdlib only).

Over layout/*report*.json, for each report carrying
provenance.input.content_hash:
  1. resolve the input stream the report names, through the explicit
     role->field table ROLE_FIELDS below (provenance.input.role selects
     which top-level field holds the path);
  2. require that field to carry a string "path" with scope "repo", and
     the named file to exist in the tree;
  3. compare the stream's sha256 against the recorded content_hash (the
     "sha256:" prefix is optional).

Fail closed: a gated report whose stream path cannot be resolved (unknown
role, none of the role's fields carrying a string path, non-"repo" scope,
named file absent) is a defect, not a skip -- that is what keeps a future
layout report from silently escaping the gate. A report with no
provenance.input.content_hash is skipped without complaint (e.g.
layout/efuse_otp_array.report.json carries no provenance block at all).
An unparseable or non-object report is a defect, not a traceback.

Scope note (deliberate and explicit, not an emergent property of
path-reading): the glob covers layout/ only, because the defect guarded
here -- a report rewritten in place beside a stream that is separately
regenerated -- is specific to reports that live beside their streams in a
regenerated tree. sim/**/records/**/report.json bundle their own netlist
inside their own append-only record directory, so a record's
report<->stream pair cannot drift once written (all such pairs match as of
8dc72be). sim/controller-sta/*.report.json may refer to historical routes. The current
100 ns report cited by the manifest is bound to the retained DEF by
sta/check_route.py.

The deck hash is deliberately NOT checked: it is engine-dependent while
signoff/klt-pin.txt does not constrain the engine
(2AMLogic/klayout-tools#5601, open; the committed drc-array report already
carries klayout_version_mismatch: true), so gating it would fail on a
fresh runner with nothing changed. Only the engine-independent input hash
is gated.

Exit 0 = clean, 1 = defects found.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

# provenance.input.role -> ordered tuple of candidate top-level fields, each
# carrying {"path": ..., "scope": "repo"} naming the report's input stream,
# tried in order (first field carrying a string "path" wins). Where each
# field comes from:
#   "file"    -- layout/drc.sh's parts=(array:efuse_otp_array
#                ctrl:efuse_otp_ctrl) writes layout/drc-$part.report.json
#                from layout/$top.gds; the report records that GDS in
#                .file.path.
#   "layout"  -- layout/lvs-ctrl.report.json (added in 2c4ca64) names its
#                as-built stream in .layout.path.
#   "netlist" -- layout/pnr.sh routes rtl/efuse_otp_ctrl.gl.v per
#                layout/pnr-request.json's "netlist"; the report records it
#                in .netlist.path.
# An explicit enumeration, not a "any *_path field" heuristic:
# sim/controller-sta/*.report.json (role "layout", out of the glob) and
# layout/pnr-report.json (role "netlist", in the glob) both carry def_path /
# gds_path / verilog_path entries pointing into the uncommitted layout/.klt/
# working directory, which a heuristic would follow or mis-resolve.
ROLE_FIELDS = {
    "layout": ("file", "layout"),
    "netlist": ("netlist",),
}

REPORT_GLOB = "layout/*report*.json"
HASH_PREFIX = "sha256:"


def normalize_hash(value):
    """Drop the optional 'sha256:' prefix so either spelling compares equal."""
    value = value.strip()
    if value.lower().startswith(HASH_PREFIX):
        value = value[len(HASH_PREFIX):]
    return value


def resolve_stream(data, role):
    """Return (path, None) for the stream the report names, else (None, reason)."""
    for field in ROLE_FIELDS[role]:
        node = data.get(field)
        if not isinstance(node, dict):
            continue
        path = node.get("path")
        if not isinstance(path, str):
            continue
        if node.get("scope") != "repo":
            return None, (f"names its input stream in .{field}.path with scope "
                          f"{node.get('scope')!r}, not \"repo\"")
        return path, None
    fields = " or ".join(f".{f}.path" for f in ROLE_FIELDS[role])
    return None, (f"role {role!r} but none of {fields} carries a string path "
                  f"(provenance.input.role requires one)")


def check(root):
    root = Path(root)
    problems = []
    gated = 0
    skipped = 0
    for path in sorted(root.glob(REPORT_GLOB)):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError) as e:
            problems.append(f"{path}: unparseable JSON ({e})")
            continue
        if not isinstance(data, dict):
            problems.append(f"{path}: top level must be a JSON object")
            continue
        provenance = data.get("provenance")
        content_hash = None
        if isinstance(provenance, dict) and isinstance(provenance.get("input"), dict):
            content_hash = provenance["input"].get("content_hash")
        if content_hash is None:
            skipped += 1
            continue
        gated += 1
        if not isinstance(content_hash, str):
            problems.append(f"{path}: provenance.input.content_hash must be a "
                            f"string, got {type(content_hash).__name__}")
            continue
        role = provenance["input"].get("role")
        if not isinstance(role, str) or role not in ROLE_FIELDS:
            problems.append(f"{path}: unknown provenance.input.role {role!r}, "
                            f"expected one of {sorted(ROLE_FIELDS)}")
            continue
        stream, problem = resolve_stream(data, role)
        if problem is not None:
            problems.append(f"{path}: {problem}")
            continue
        stream_file = root / stream
        if not stream_file.is_file():
            problems.append(f"{path}: names input stream {stream}, which is "
                            f"not present in the tree")
            continue
        actual = hashlib.sha256(stream_file.read_bytes()).hexdigest()
        if normalize_hash(content_hash) != actual:
            problems.append(f"{path}: recorded input {content_hash} does not "
                            f"match stream {stream} (actual "
                            f"sha256:{actual}) -- was the report re-run after "
                            f"the stream was regenerated?")
    return problems, gated, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    problems, gated, skipped = check(args.root)
    for p in problems:
        print(f"FAIL: {p}")
    if problems:
        return 1
    note = f"; {skipped} skipped (no provenance.input.content_hash)" if skipped else ""
    if gated == 0:
        print(f"OK: no report carries a recorded input hash, "
              f"report-input check passes vacuously{note}")
    else:
        print(f"OK: {gated} report input hash(es) match the streams they "
              f"name{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
