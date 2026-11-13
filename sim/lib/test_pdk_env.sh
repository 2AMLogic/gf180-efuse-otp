#!/usr/bin/env bash
# Self-test for pdk_env.sh: pin matches, SOURCES at another revision, no tree.
# Uses a fake tree under a temp CIEL_ROOT; the fake revision is a fixture only.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
pin="$(jq -er .open_pdks_revision "$here/../pdk.json")"
variant="$(jq -er .variant "$here/../pdk.json")"
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
  for f in sm141064.ngspice sm141064.spice design.ngspice; do echo "$f" > "$vdir/$f"; done
  "$setup" "$root/ciel/gf180mcu/versions/$pin/gf180mcuD/libs.tech/ngspice" "$vdir"
  out="$(CIEL_ROOT="$root" bash -c 'source "$1" && pdk_fleet_check && echo "LIB=$PDK_FLEET_LIB_DIR"' _ "$here/pdk_env.sh" 2>&1)"; rc=$?
  check "fleet $name" "$want" "$rc"
  [[ "$out" == *"$sub"* ]] || { echo "FAIL fleet $name message: $out"; fail=1; }
}
copy_d() { mkdir -p "$1"; cp "$2"/* "$1"/; }
differ_d() { copy_d "$1" "$2"; echo changed > "$1/design.ngspice"; }
no_d() { :; }
fleet_case match 0 "LIB=$tmp/fleet-match/ciel/gf180mcu/versions/$pin/gf180mcuD/libs.tech/ngspice" copy_d
fleet_case differ 1 "design.ngspice differs between gf180mcuC and gf180mcuD" differ_d
fleet_case missing-d 1 "differs between gf180mcuC and gf180mcuD" no_d
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

exit "$fail"
