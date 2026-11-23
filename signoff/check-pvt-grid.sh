#!/usr/bin/env bash
# decision-0005 PVT grid binding check: the four PVT_* constants sim/lib/pdk_env.sh
# exports must equal the grid stated by the ratified spec/efuse-otp.md "PVT corners"
# row, read through signoff/item6-digital-spec.json (the extract whose binding to the
# spec check-item6-digital.sh owns; the one verbatim-line assertion needed here is
# re-stated so this check stands alone in the job).
#   - the pvt-corners row text still appears verbatim as a line of spec/efuse-otp.md
#   - the four axes parsed from that row (process names in order, the temperature
#     list, the logic/sense and program supply triplets) equal the values the
#     constants export when sim/lib/pdk_env.sh is sourced
# Exit 0 = bound, 1 = stale, inconsistent or unparseable. When it fails after a spec
# amendment (which needs a decision record), update sim/lib/pdk_env.sh and the golden
# literals in sim/lib/test_pdk_env.sh together with the spec and its extract.
set -euo pipefail
cd "$(dirname "$0")/.."

# The benches consume the exported constants, so read them by sourcing the real
# file, never by regexing the assignment lines. With no PDK tree present the
# source returns 1 after exporting the constants -- exactly the state a bare
# harness runner is in -- so probe under set +e; stdout is the four JSON
# literals, one per line.
grid="$(bash -c 'set +e; source "$1"; printf "%s\n" "${PVT_PROCESSES-}" "${PVT_TEMPERATURES_C-}" "${PVT_SUPPLY_3V3-}" "${PVT_SUPPLY_5V0-}"' _ sim/lib/pdk_env.sh)" \
  || { echo "FAIL: could not source sim/lib/pdk_env.sh to read the PVT_* constants" >&2; exit 1; }

python3 -I - "$grid" <<'PY'
import json, re, sys

AXES = [
    ("processes", "PVT_PROCESSES"),
    ("temperatures", "PVT_TEMPERATURES_C"),
    ("logic/sense supply 3.3 V", "PVT_SUPPLY_3V3"),
    ("program supply 5.0 V", "PVT_SUPPLY_5V0"),
]

ex = json.load(open("signoff/item6-digital-spec.json", encoding="utf-8"))
row = next((r for r in ex["rows"] if r["id"] == "pvt-corners"), None)
if row is None:
    sys.exit("FAIL: signoff/item6-digital-spec.json has no pvt-corners row")
text = row["text"]

spec_lines = set(open("spec/efuse-otp.md", encoding="utf-8").read().split("\n"))
if text not in spec_lines:
    print("FAIL: the pvt-corners row no longer appears verbatim as a line of "
          "spec/efuse-otp.md; regenerate signoff/item6-digital-spec.json (see "
          "check-item6-digital.sh)", file=sys.stderr)
    sys.exit(1)

bad = []
spec = {}

m = re.search(r"Process ((?:`[^`]+`(?:, )?)+);", text)
if not m:
    bad.append("cannot parse the process list from the pvt-corners row "
               "(expected backticked names after 'Process ')")
else:
    spec["processes"] = re.findall(r"`([^`]+)`", m.group(1))
    if not spec["processes"]:
        bad.append("the pvt-corners row names no backticked process after 'Process '")

m = re.search(r"T = ([^;]+) °C", text)
if not m:
    bad.append("cannot parse the temperature list from the pvt-corners row "
               "(expected 'T = ..., ..., ... °C')")
else:
    # The spec row writes minus as U+2212 MINUS SIGN, not ASCII '-'.
    temps = m.group(1).replace("−", "-")
    try:
        spec["temperatures"] = [float(t.strip()) for t in temps.split(",")]
    except ValueError:
        bad.append("cannot parse the temperature list %r from the pvt-corners row" % temps)

triples = re.findall(r"\((\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)+) V\)", text)
if len(triples) != 2:
    bad.append("expected exactly two '(a/b/c V)' supply triplets in the pvt-corners "
               "row, found %d" % len(triples))
else:
    spec["logic/sense supply 3.3 V"] = [float(x) for x in triples[0].split("/")]
    spec["program supply 5.0 V"] = [float(x) for x in triples[1].split("/")]

lines = sys.argv[1].split("\n")
if len(lines) != 4 or not all(line.strip() for line in lines):
    bad.append("sourcing sim/lib/pdk_env.sh did not yield four non-empty PVT_* values "
               "(got %r); are PVT_PROCESSES/PVT_TEMPERATURES_C/PVT_SUPPLY_3V3/"
               "PVT_SUPPLY_5V0 still assigned before the main block?" % lines)
else:
    for (axis, constant), raw in zip(AXES, lines):
        try:
            value = json.loads(raw)
        except ValueError:
            bad.append("%s from sim/lib/pdk_env.sh is not JSON: %r" % (constant, raw))
            continue
        if axis not in spec:
            continue  # the spec parse failure above is already reported
        if spec[axis] != value:
            bad.append("%s axis disagrees: spec row parses to %r, sim/lib/pdk_env.sh "
                       "%s exports %r" % (axis, spec[axis], constant, value))

if bad:
    for b in bad:
        print("FAIL:", b, file=sys.stderr)
    sys.exit(1)
print("OK: decision-0005 PVT grid in sim/lib/pdk_env.sh bound to the "
      "spec/efuse-otp.md pvt-corners row (processes %r in order; temperatures %r C; "
      "supply 3.3 V %r; supply 5.0 V %r)"
      % tuple(spec[a] for a, _ in AXES))
PY
