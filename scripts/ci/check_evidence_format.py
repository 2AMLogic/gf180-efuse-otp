#!/usr/bin/env python3
"""Check evidence-directory structure and sim/ record format (stdlib only).

Checks:
  1. each evidence directory has a README.md;
  2. each sim/*/records/*/record.json parses, is a JSON object, carries the
     required fields (including a PDK revision), and holds repo-relative
     paths only.

The record count is reported, and zero matched records is a failure, not a
pass: a checkout with committed records and zero matches is the discovery
defect this check exists to catch (#118). The 11 record directories listed
in LEGACY_DIRS were committed before the three-field requirement was
enforced and are append-only, so they are exempt from exactly the two
fields they never carried; every other record, including a new stamp under
the same bench, requires all three.
Exit 0 = clean, 1 = defects found.
"""
import argparse
import json
import re
import sys
from pathlib import Path

EVIDENCE_DIRS = ("design", "layout", "measurements", "rtl", "sim", "spec",
                 "verification")
# Align with the fields the first sim record format (#4) specifies.
REQUIRED_FIELDS = ("pdk_revision", "tool_versions", "corners")
# Operator ruling on #118 (2026-11-23): keep all three required fields for
# new records and grandfather the 11 existing record directories by this
# explicit list. sim/ records are append-only, so these cannot be edited to
# comply; the exemption is by exact repo-relative directory and covers only
# the two fields those records never carried -- pdk_revision and the
# repo-relative path rules still apply to them.
LEGACY_EXEMPT_FIELDS = ("tool_versions", "corners")
LEGACY_DIRS = frozenset((
    "sim/corner-verification/records/20261030T230649Z-f6eeac7",
    "sim/corner-verification/records/20261108T235750Z-f6eeac7",
    "sim/corner-verification/records/20261108T235928Z-f6eeac7",
    "sim/pdk-smoke/records/20261017T225702Z-f6eeac7",
    "sim/program-select/records/20261023T174839Z-f6eeac7",
    "sim/sense-margin/records/20261030T223615Z-f6eeac7",
    "sim/sense-margin/records/20261105T054826Z-f6eeac7",
    "sim/sense-margin/records/20261105T055051Z-f6eeac7",
    "sim/sense-margin/records/20261105T071054Z-f6eeac7",
    "sim/sense-margin/records/20261105T083938Z-f6eeac7",
    "sim/sense-margin/records/20261109T002043Z-f6eeac7",
))

_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")


def bad_path(value):
    """Return a reason if the string is not a repo-relative path, else None."""
    if "://" in value:  # URLs are not paths
        return None
    if value.startswith(("/", "\\", "~")) or _DRIVE.match(value):
        return "absolute path"
    if ".." in re.split(r"[\\/]", value):
        return "parent traversal"
    return None


def walk_strings(node, where="$"):
    if isinstance(node, str):
        yield where, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from walk_strings(v, f"{where}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_strings(v, f"{where}[{i}]")


def check_record(path, exempt=()):
    problems = []
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        return [f"{path}: unparseable JSON ({e})"]
    if not isinstance(data, dict):
        return [f"{path}: top level must be a JSON object"]
    for field in REQUIRED_FIELDS:
        if field in exempt:
            continue
        if data.get(field) in (None, "", [], {}):
            problems.append(f"{path}: missing required field '{field}'")
    for where, value in walk_strings(data):
        reason = bad_path(value)
        if reason:
            problems.append(f"{path}: {where} = {value!r} is not repo-relative ({reason})")
    return problems


def check(root):
    root = Path(root)
    problems = []
    for d in EVIDENCE_DIRS:
        if not (root / d / "README.md").is_file():
            problems.append(f"{d}/: missing README.md")
    records = sorted((root / "sim").glob("*/records/*/record.json"))
    for rec in records:
        rel = rec.relative_to(root).parent.as_posix()
        exempt = LEGACY_EXEMPT_FIELDS if rel in LEGACY_DIRS else ()
        problems += check_record(rec, exempt)
    if not records:
        problems.append("sim/: no record matches sim/*/records/*/record.json; "
                        "zero matches is a failure, not a vacuous pass (#118)")
    return problems, len(records)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    problems, n = check(args.root)
    for p in problems:
        print(f"FAIL: {p}")
    if problems:
        return 1
    print(f"OK: evidence READMEs present; {n} sim record(s) well-formed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
