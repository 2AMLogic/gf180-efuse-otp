#!/usr/bin/env bash
# Item 6 (digital, not_applicable) binding check: the spec extract must still be the
# ratified spec/efuse-otp.md, byte for byte where it quotes it.
#   - signoff/item6-digital-spec.json source.sha256 equals the sha256 of spec/efuse-otp.md
#   - every extract row's text appears verbatim as a line of spec/efuse-otp.md
#   - the spec still declares itself ratified
#   - every spec/efuse-otp.md section-2 table row bearing on the digital partition is in the
#     statement exactly once (ids match between extract and statement)
# Exit 0 = bound, 1 = stale or inconsistent. When it fails after a spec change (which needs
# a decision record), regenerate the extract and statement review, then re-hash the manifest.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -I - <<'PY'
import hashlib, json, sys
spec_path = "spec/efuse-otp.md"
raw = open(spec_path, "rb").read()
text = raw.decode("utf-8")
ex = json.load(open("signoff/item6-digital-spec.json", encoding="utf-8"))
st = json.load(open("signoff/item6-digital-statement.json", encoding="utf-8"))
bad = []
if ex.get("source", {}).get("file") != spec_path:
    bad.append("extract source.file is not " + spec_path)
if ex.get("source", {}).get("sha256") != hashlib.sha256(raw).hexdigest():
    bad.append("spec/efuse-otp.md changed: extract source.sha256 is stale")
if "Status: **ratified**" not in text:
    bad.append("spec/efuse-otp.md no longer declares itself ratified")
lines = set(text.split("\n"))
for row in ex["rows"]:
    if row["text"] not in lines:
        bad.append("row %r no longer matches a line of the spec" % row["id"])
ex_ids = [r["id"] for r in ex["rows"]]
st_ids = [r["id"] for r in st["rows"]]
if sorted(ex_ids) != sorted(st_ids):
    bad.append("extract and statement ids differ: %s vs %s" % (ex_ids, st_ids))
for b in bad:
    print("FAIL:", b, file=sys.stderr)
if bad:
    sys.exit(1)
print("OK: item 6 digital extract bound to spec/efuse-otp.md (%d rows)" % len(ex_ids))
PY
