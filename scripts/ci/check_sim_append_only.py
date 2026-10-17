#!/usr/bin/env python3
"""Fail if a change modifies, deletes or renames a committed sim/ record.

Compares BASE...HEAD and rejects any non-Added path under
sim/**/records/. Adding records is allowed. A BASE of all zeros (first
push) skips the check with a notice. Needs full history (fetch-depth: 0).
"""
import argparse
import re
import subprocess
import sys

RECORD = re.compile(r"^sim/(?:.+/)?records/.+")


def violations(name_status):
    bad = []
    for line in name_status.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0] != "A" and RECORD.match(parts[1]):
            bad.append((parts[0], parts[1]))
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", required=True, help="base ref or SHA")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    if re.fullmatch(r"0+", args.base):
        print("NOTICE: base is all zeros (first push); append-only check skipped")
        return 0
    out = subprocess.run(
        ["git", "-C", args.root, "diff", "--name-status", "--no-renames",
         f"{args.base}...{args.head}", "--", "sim/"],
        capture_output=True, text=True)
    if out.returncode != 0:
        print(f"FAIL: git diff failed: {out.stderr.strip()}")
        return 1
    bad = violations(out.stdout)
    for status, path in bad:
        print(f"FAIL: {path} was {status} (sim records are append-only)")
    if bad:
        return 1
    print("OK: no sim record was modified or deleted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
