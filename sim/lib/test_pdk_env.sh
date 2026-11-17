#!/usr/bin/env bash
# Self-test for pdk_env.sh: pin matches, SOURCES at another revision, no tree,
# the fleet check against fake C and D trees (every listed file compared,
# nothing beyond the list, a missing or empty list fails), and the provenance
# statement naming exactly the files the check compares.
# Uses a fake tree under a temp CIEL_ROOT; the fake revision is a fixture only.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
pin="$(jq -er .open_pdks_revision "$here/../pdk.json")"
variant="$(jq -er .variant "$here/../pdk.json")"
mapfile -t fleet_files < <(jq -r '.fleet_checked_model_files[]' "$here/../pdk.json")
FIXTURE_OTHER_REV=0000000000000000000000000000000000000000   # fixture, never a real pin
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
fail=0
check() { # name expected-rc actual-rc
  if [[ "$2" == "$3" ]]; then echo "PASS $1"; else echo "FAIL $1 (rc=$3, want $2)"; fail=1; fi
}

mkdir -p "$tmp/ok/ciel/gf180mcu/versions/$pin/$variant"
echo "open_pdks $pin" > "$tmp/ok/ciel/gf180mcu/versions/$pin/$variant/SOURCES"
out="$(CIEL_ROOT="$tmp/ok" "$here/pdk_env.sh" 2>&1)"; rc=$?
check "match exits 0" 0 "$rc"
[[ "$out" == "$tmp/ok/ciel/gf180mcu/versions/$pin/$variant" ]] || { echo "FAIL match prints variant dir"; fail=1; }

mkdir -p "$tmp/bad/ciel/gf180mcu/versions/$pin/$variant"
echo "open_pdks $FIXTURE_OTHER_REV" > "$tmp/bad/ciel/gf180mcu/versions/$pin/$variant/SOURCES"
out="$(CIEL_ROOT="$tmp/bad" "$here/pdk_env.sh" 2>&1)"; rc=$?
check "SOURCES mismatch exits non-zero" 1 "$rc"
[[ "$out" == *"expected 'open_pdks $pin'"* ]] || { echo "FAIL mismatch message: $out"; fail=1; }

mkdir -p "$tmp/empty"
out="$(CIEL_ROOT="$tmp/empty" "$here/pdk_env.sh" 2>&1)"; rc=$?
check "no tree exits non-zero" 1 "$rc"
[[ "$out" == *"no tree for pinned revision"* ]] || { echo "FAIL missing message: $out"; fail=1; }

# pdk_fleet_check: sourced function; run against fake C and D trees.
fleet_case() { # name want-rc want-substr setup-fn
  local name="$1" want="$2" sub="$3" setup="$4" root="$tmp/fleet-$1" vdir out rc f
  vdir="$root/ciel/gf180mcu/versions/$pin/$variant/libs.tech/ngspice"
  mkdir -p "$vdir"; echo "open_pdks $pin" > "$root/ciel/gf180mcu/versions/$pin/$variant/SOURCES"
  for f in "${fleet_files[@]}"; do echo "$f" > "$vdir/$f"; done
  "$setup" "$root/ciel/gf180mcu/versions/$pin/gf180mcuD/libs.tech/ngspice" "$vdir"
  out="$(CIEL_ROOT="$root" bash -c 'source "$1" && pdk_fleet_check && echo "LIB=$PDK_FLEET_LIB_DIR"' _ "$here/pdk_env.sh" 2>&1)"; rc=$?
  check "fleet $name" "$want" "$rc"
  [[ "$out" == *"$sub"* ]] || { echo "FAIL fleet $name message: $out"; fail=1; }
}
copy_d() { mkdir -p "$1"; cp "$2"/* "$1"/; }
differ_d() { copy_d "$1" "$2"; echo changed > "$1/${fleet_files[0]}"; }
no_d() { :; }
fleet_case match 0 "LIB=$tmp/fleet-match/ciel/gf180mcu/versions/$pin/gf180mcuD/libs.tech/ngspice" copy_d
fleet_case differ 1 "${fleet_files[0]} differs between gf180mcuC and gf180mcuD" differ_d
fleet_case missing-d 1 "differs between gf180mcuC and gf180mcuD" no_d
# every listed file is really compared: corrupting any one of them in D fails,
# naming it
for f in "${fleet_files[@]}"; do
  root="$tmp/fleet-each-$f"
  vdir="$root/ciel/gf180mcu/versions/$pin/$variant/libs.tech/ngspice"
  ddir="$root/ciel/gf180mcu/versions/$pin/gf180mcuD/libs.tech/ngspice"
  mkdir -p "$vdir"; echo "open_pdks $pin" > "$root/ciel/gf180mcu/versions/$pin/$variant/SOURCES"
  for g in "${fleet_files[@]}"; do echo "$g" > "$vdir/$g"; done
  copy_d "$ddir" "$vdir"; echo changed > "$ddir/$f"
  out="$(CIEL_ROOT="$root" bash -c 'source "$1" && pdk_fleet_check' _ "$here/pdk_env.sh" 2>&1)"; rc=$?
  check "fleet compares $f" 1 "$rc"
  [[ "$out" == *"$f differs between gf180mcuC and gf180mcuD"* ]] || { echo "FAIL fleet compares $f message: $out"; fail=1; }
done
# and nothing beyond the list: a differing file not in it must not fail the
# check (it would if the loop restated its own list)
root="$tmp/fleet-decoy"
vdir="$root/ciel/gf180mcu/versions/$pin/$variant/libs.tech/ngspice"
ddir="$root/ciel/gf180mcu/versions/$pin/gf180mcuD/libs.tech/ngspice"
mkdir -p "$vdir"; echo "open_pdks $pin" > "$root/ciel/gf180mcu/versions/$pin/$variant/SOURCES"
for g in "${fleet_files[@]}"; do echo "$g" > "$vdir/$g"; done
echo decoy > "$vdir/zz-decoy-not-checked.spice"
copy_d "$ddir" "$vdir"; echo decoy-changed > "$ddir/zz-decoy-not-checked.spice"
out="$(CIEL_ROOT="$root" bash -c 'source "$1" && pdk_fleet_check' _ "$here/pdk_env.sh" 2>&1)"
check "fleet ignores files outside the list" 0 "$?"
# a missing or empty list must fail the check, not pass it vacuously; run
# against a fixture copy of pdk_env.sh with its own pdk.json
list_case() { # name jq-expr want-rc want-substr
  local name="$1" expr="$2" want="$3" sub="$4" d="$tmp/list-$1" out rc
  mkdir -p "$d/lib"; cp "$here/pdk_env.sh" "$d/lib/pdk_env.sh"
  jq "$expr" "$here/../pdk.json" > "$d/pdk.json"
  out="$(CIEL_ROOT="$tmp/ok" bash -c 'source "$1" && pdk_fleet_check' _ "$d/lib/pdk_env.sh" 2>&1)"; rc=$?
  check "fleet list $name" "$want" "$rc"
  [[ "$out" == *"$sub"* ]] || { echo "FAIL fleet list $name message: $out"; fail=1; }
}
list_case empty '.fleet_checked_model_files = []' 1 "fleet_checked_model_files in sim/pdk.json is empty"
list_case missing 'del(.fleet_checked_model_files)' 1 "cannot read fleet_checked_model_files"
# the provenance statement and the check must name exactly the same files: the
# one list in sim/pdk.json drives both, so rendered == listed == compared
python3 - "$here" "$here/../pdk.json" <<'PYEOF' || { echo "FAIL variant_simulated names the compared files"; fail=1; }
import json, sys
sys.path.insert(0, sys.argv[1])
import bench_record
listed = json.load(open(sys.argv[2]))["fleet_checked_model_files"]
names = bench_record.VARIANT_SIMULATED.split("(fleet image; ", 1)[1].split(" byte-identical", 1)[0].split(", ")
if names != list(listed):
    print(f"variant_simulated names {names}, pdk.json lists {listed}")
    sys.exit(1)
PYEOF
# sourcing alone must not require a D tree (tree "ok" above has none)
CIEL_ROOT="$tmp/ok" bash -c 'source "$1"' _ "$here/pdk_env.sh" >/dev/null 2>&1; check "source without D tree exits 0" 0 "$?"

# bench helpers: sourced functions, run in subshells against the ok tree.
out="$(CIEL_ROOT="$tmp/ok" bash -c 'source "$1"; bench_parse_args --dry-run; echo "dry=$dry"; bench_parse_args; echo "dry=$dry"' _ "$here/pdk_env.sh" 2>&1)"
[[ "$out" == $'dry=1\ndry=0' ]] || { echo "FAIL bench_parse_args: $out"; fail=1; }
out="$(CIEL_ROOT="$tmp/ok" bash -c 'source "$1"; bench_parse_args --bogus' _ "$here/pdk_env.sh" 2>&1)"; rc=$?
check "bench_parse_args rejects unknown arg" 2 "$rc"
[[ "$out" == "usage: run.sh [--dry-run]" ]] || { echo "FAIL usage message: $out"; fail=1; }

printf '.subckt a x\nR1 x 0 1\n.ends\n.subckt b y\nR2 y 0 2\n.ends\n' > "$tmp/nl.spice"
out="$(CIEL_ROOT="$tmp/ok" bash -c 'source "$1"; bench_subckt "$2" b' _ "$here/pdk_env.sh" "$tmp/nl.spice" 2>&1)"
[[ "$out" == $'.subckt b y\nR2 y 0 2\n.ends' ]] || { echo "FAIL bench_subckt: $out"; fail=1; }

rd="$tmp/records"
out="$(CIEL_ROOT="$tmp/ok" bash -c 'source "$1"; bench_new_record_dir "$2" 0; echo "$rec"; [[ -d "$rec" ]] && [[ "$rec" == "$2/$stamp-${PDK_REVISION:0:7}" ]]' _ "$here/pdk_env.sh" "$rd" 2>&1)"; rc=$?
check "bench_new_record_dir creates record dir" 0 "$rc"
# same stamp again must fail, not overwrite
CIEL_ROOT="$tmp/ok" bash -c 'source "$1"; date() { echo FIXEDSTAMP; }; bench_new_record_dir "$2" 0; bench_new_record_dir "$2" 0' _ "$here/pdk_env.sh" "$rd" >/dev/null 2>&1
check "bench_new_record_dir refuses an existing record" 1 "$?"
out="$(CIEL_ROOT="$tmp/ok" bash -c 'source "$1"; bench_new_record_dir "$2/none" 1; [[ -d "$rec" && ! -e "$2/none" ]]' _ "$here/pdk_env.sh" "$rd" 2>&1)"
check "bench_new_record_dir dry run uses a temp dir" 0 "$?"

# bench_dry_run / bench_submit_set: a fake klt on PATH records its argv.
fb="$tmp/fakebin"; mkdir -p "$fb"
cat > "$fb/klt" <<'KLT'
#!/usr/bin/env bash
echo "$*" >> "$FAKE_KLT_LOG"
[[ "$1" == "sim" && "$2" == "--dry-run" ]] && echo '{"unit_count":1,"backend":"batch","warnings":[]}'
exit "${FAKE_KLT_RC:-0}"
KLT
chmod +x "$fb/klt"
export FAKE_KLT_LOG="$tmp/klt.log"; : > "$FAKE_KLT_LOG"
out="$(PATH="$fb:$PATH" CIEL_ROOT="$tmp/ok" bash -c 'source "$1"; bench_dry_run a.json b.json' _ "$here/pdk_env.sh" 2>&1)"; rc=$?
check "bench_dry_run exits 0" 0 "$rc"
[[ "$(grep -c -- '--dry-run --format json --backend batch' "$FAKE_KLT_LOG")" == 2 ]] || { echo "FAIL bench_dry_run argv: $(cat "$FAKE_KLT_LOG")"; fail=1; }
[[ "$out" == *'"unit_count":1'* ]] || { echo "FAIL bench_dry_run output: $out"; fail=1; }
for want in 0 3 4 2; do
  : > "$FAKE_KLT_LOG"; mkdir -p "$tmp/rec$want"
  out="$(FAKE_KLT_RC=$want PATH="$fb:$PATH" CIEL_ROOT="$tmp/ok" bash -c 'set -e; source "$1"; bench_submit_set "$2" a.json b.json; echo "rc=$rc"' _ "$here/pdk_env.sh" "$tmp/rec$want" 2>&1)"; got=$?
  if [[ $want -eq 2 ]]; then
    check "bench_submit_set exits on tool failure" 2 "$got"
    [[ "$out" == *"klt sim --batch-set failed (rc=2)"* ]] || { echo "FAIL submit failure message: $out"; fail=1; }
  else
    check "bench_submit_set tolerates rc=$want" 0 "$got"
    [[ "$out" == "rc=$want" ]] || { echo "FAIL submit rc=$want: $out"; fail=1; }
  fi
  grep -q -- "--batch-set a.json b.json --max-in-flight 4 --capacity-retries 3 --wait-for-capacity 600 -o $tmp/rec$want/sets" "$FAKE_KLT_LOG" || { echo "FAIL submit argv: $(cat "$FAKE_KLT_LOG")"; fail=1; }
done

# The decision-0005 grid constants (pdk_env.sh): each bench interpolates them
# into its request builder with jq --argjson and keeps its own supply-axis
# names and sections map, so every emitted corners: object must be byte for
# byte the hand-typed one it replaced. The expected literals are the corners
# of the committed pre-refactor requests (e.g.
# sim/corner-verification/records/20261108T235928Z-f6eeac7/prog_rf140.json).
corners_case() { # name efuse-json want-json jq-program
  local name="$1" efuse="$2" want="$3" prog="$4" out
  out="$(CIEL_ROOT="$tmp/ok" bash -c 'source "$1"; jq -cn \
    --argjson p "$PVT_PROCESSES" --argjson t "$PVT_TEMPERATURES_C" \
    --argjson v33 "$PVT_SUPPLY_3V3" --argjson v5 "$PVT_SUPPLY_5V0" \
    --argjson efuse "$3" "$2"' _ "$here/pdk_env.sh" "$prog" "$efuse" 2>&1)"
  if [[ "$out" == "$want" ]]; then echo "PASS corners $name"; else echo "FAIL corners $name: $out"; fail=1; fi
}
corners_case sense true \
  '{"process":[{"name":"typical","sections":["typical"]},{"name":"ff","sections":["ff"]},{"name":"ss","sections":["ss"]},{"name":"fs","sections":["fs"]},{"name":"sf","sections":["sf"]}],"supply_v":{"vdd33":[2.97,3.30,3.63]},"temperature_c":[-40,25,125]}' \
  '{process:($p|map({name:., sections:[.]})), supply_v:{vdd33:$v33}, temperature_c:$t}'
corners_case program-select true \
  '{"process":[{"name":"typical","sections":["typical","efuse"]},{"name":"ff","sections":["ff","efuse"]},{"name":"ss","sections":["ss","efuse"]},{"name":"fs","sections":["fs","efuse"]},{"name":"sf","sections":["sf","efuse"]}],"supply_v":{"vdd":[4.5,5.0,5.5]},"temperature_c":[-40,25,125]}' \
  '{process:($p|map({name:., sections:[., "efuse"]})), supply_v:{vdd:$v5}, temperature_c:$t}'
corners_case corner-verification-efuse true \
  '{"process":[{"name":"typical","sections":["typical","efuse"]},{"name":"ff","sections":["ff","efuse"]},{"name":"ss","sections":["ss","efuse"]},{"name":"fs","sections":["fs","efuse"]},{"name":"sf","sections":["sf","efuse"]}],"supply_v":{"vdd33":[2.97,3.30,3.63],"vprog":[4.5,5.0,5.5]},"temperature_c":[-40,25,125]}' \
  '{process:($p|map({name:., sections:([.] + (if $efuse then ["efuse"] else [] end))})), supply_v:{vdd33:$v33, vprog:$v5}, temperature_c:$t}'
corners_case corner-verification-no-efuse false \
  '{"process":[{"name":"typical","sections":["typical"]},{"name":"ff","sections":["ff"]},{"name":"ss","sections":["ss"]},{"name":"fs","sections":["fs"]},{"name":"sf","sections":["sf"]}],"supply_v":{"vdd33":[2.97,3.30,3.63],"vprog":[4.5,5.0,5.5]},"temperature_c":[-40,25,125]}' \
  '{process:($p|map({name:., sections:([.] + (if $efuse then ["efuse"] else [] end))})), supply_v:{vdd33:$v33, vprog:$v5}, temperature_c:$t}'

exit "$fail"
