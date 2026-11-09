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

exit "$fail"
