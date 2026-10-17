#!/usr/bin/env python3
"""Check evidence-directory structure and sim/ record format (stdlib only).

Checks:
  1. each evidence directory has a README.md;
  2. each sim/**/records/*.json parses, carries the required fields
     (including a PDK revision), and holds repo-relative paths only.

With no records yet, leg 2 passes vacuously and says so.
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


def check_record(path):
    problems = []
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        return [f"{path}: unparseable JSON ({e})"]
    if not isinstance(data, dict):
        return [f"{path}: top level must be a JSON object"]
    for field in REQUIRED_FIELDS:
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
    records = sorted((root / "sim").glob("**/records/*.json"))
    for rec in records:
        problems += check_record(rec)
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
    if n == 0:
        print("OK: evidence READMEs present; no sim records yet, record-format check passes vacuously")
    else:
        print(f"OK: evidence READMEs present; {n} sim record(s) well-formed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
