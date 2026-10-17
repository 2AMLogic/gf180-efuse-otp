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

exit "$fail"
