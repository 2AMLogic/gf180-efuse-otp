#!/usr/bin/env bash
# Self-test for klt.sh: the uvx-absent preflight (exit 2, message), the [yield]
# extras splice, klt()/klt_python() argv passthrough and KLT_ARGV through a fake
# uvx, the pin read exactly once and actually exported (the declare -x
# attribute, not mere set-ness), KLT_NO_FUNCTION=1 as a sourcing-local
# assignment (no function facets: the sim benches keep their bare host-klt
# calls) with its exported form ignored under a warning, and pin resolution
# from a foreign cwd (BASH_SOURCE, not cwd). Modelled on sim/lib/test_pdk_env.sh.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
pin="$(cat "$here/klt-pin.txt")"
version="${pin##*==}"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
fail=0
check() { # name expected-rc actual-rc
  if [[ "$2" == "$3" ]]; then echo "PASS $1"; else echo "FAIL $1 (rc=$3, want $2)"; fail=1; fi
}
# grep -F: the expected strings contain [] and ==, not regexes; substring match.
lit() { # name string haystack
  if grep -qF -- "$2" <<<"$3"; then return 0; else echo "FAIL $1: $3"; fail=1; fi
}
lit_not() { # name string haystack  (fails when the string IS found)
  if grep -qF -- "$2" <<<"$3"; then echo "FAIL $1 (found: $2)"; fail=1; fi
}
bash_bin="$(command -v bash)"

# source defines every facet; KLT_PIN is exported (the declare -x attribute --
# [[ -n ${KLT_PIN+x} ]] is true for any set variable, exported or not).
out="$(bash -c '. "$1"; echo "pin=$KLT_PIN"; echo "argv=$KLT_ARGV";
  echo "yield=${KLT_YIELD[*]}"; echo "klt=$(type -t klt)"; echo "py=$(type -t klt_python)";
  declare -p KLT_PIN' _ "$here/klt.sh" 2>&1)"; rc=$?
check "source exits 0" 0 "$rc"
lit "pin facet" "pin=$pin" "$out"
lit "argv facet" "argv=uvx --from $pin klt" "$out"
lit "yield facet" "yield=uvx --from klayout-tools[yield]==$version klt" "$out"
lit "klt facet" "klt=function" "$out"
lit "klt_python facet" "py=function" "$out"
lit "KLT_PIN exported" "declare -x KLT_PIN" "$out"

# uvx absent: exit 2 with the verification/run.sh message, before anything else.
nb="$tmp/nouvx"; mkdir -p "$nb"
for t in dirname cat; do ln -s "$(command -v "$t")" "$nb/$t"; done
out="$(PATH="$nb" "$bash_bin" -c '. "$1"' _ "$here/klt.sh" 2>&1)"; rc=$?
check "no uvx exits 2" 2 "$rc"
lit "no-uvx message" "uvx not found; the pinned klt in signoff/klt-pin.txt is reached through it" "$out"

# pin file missing: exit 2 (BASH_SOURCE resolves inside the fixture tree).
mkdir -p "$tmp/tree/signoff"; cp "$here/klt.sh" "$tmp/tree/signoff/klt.sh"
out="$(bash -c '. "$1"' _ "$tmp/tree/signoff/klt.sh" 2>&1)"; rc=$?
check "missing pin exits 2" 2 "$rc"
lit "missing-pin message" "pin file missing" "$out"

# klt() and klt_python() reach uvx --from <pin> with the caller's argv.
fb="$tmp/fakebin"; mkdir -p "$fb"
cat > "$fb/uvx" <<'UVX'
#!/usr/bin/env bash
echo "$*" >> "$FAKE_UVX_LOG"
UVX
chmod +x "$fb/uvx"
export FAKE_UVX_LOG="$tmp/uvx.log"; : > "$FAKE_UVX_LOG"
PATH="$fb:$PATH" bash -c '. "$1"; klt drc --check x.json' _ "$here/klt.sh" 2>&1; check "klt passthrough exits 0" 0 "$?"
PATH="$fb:$PATH" bash -c '. "$1"; klt_python -I -c "import sys" y.gds' _ "$here/klt.sh" 2>&1; check "klt_python passthrough exits 0" 0 "$?"
lit "klt argv" "--from $pin klt drc --check x.json" "$(cat "$FAKE_UVX_LOG")"
lit "klt_python argv" "--from $pin python -I -c import sys y.gds" "$(cat "$FAKE_UVX_LOG")"

# the pin file is read exactly once, at source (cat runs once, not per call).
cc="$tmp/countcat"; mkdir -p "$cc"
cat > "$cc/cat" <<CAT
#!/usr/bin/env bash
echo "\$*" >> "$tmp/cat.log"
exec /usr/bin/cat "\$@"
CAT
chmod +x "$cc/cat"; : > "$tmp/cat.log"
PATH="$cc:$PATH" bash -c '. "$1"' _ "$here/klt.sh" 2>&1; check "source with counting cat exits 0" 0 "$?"
[[ "$(wc -l < "$tmp/cat.log")" == 1 ]] || { echo "FAIL pin read $(wc -l < "$tmp/cat.log") times: $(cat "$tmp/cat.log")"; fail=1; }

# KLT_NO_FUNCTION=1: no function facets, pin and extras still defined.
out="$(PATH="$fb:$PATH" bash -c 'KLT_NO_FUNCTION=1; . "$1";
  echo "klt=$(type -t klt)"; echo "py=$(type -t klt_python)"; echo "pin=$KLT_PIN"; echo "yield=${KLT_YIELD[*]}"' \
  _ "$here/klt.sh" 2>&1)"; rc=$?
check "KLT_NO_FUNCTION source exits 0" 0 "$rc"
lit_not "klt defined despite KLT_NO_FUNCTION" "klt=function" "$out"
lit_not "klt_python defined despite KLT_NO_FUNCTION" "py=function" "$out"
lit "KLT_NO_FUNCTION pin" "pin=$pin" "$out"
lit "KLT_NO_FUNCTION yield" "yield=uvx --from klayout-tools[yield]==$version klt" "$out"

# an exported KLT_NO_FUNCTION is inherited from the environment: ignored, both
# facets stay defined, one warning names the variable -- an environment
# variable must not be able to switch a signoff script off the pinned klt.
out="$(KLT_NO_FUNCTION=1 bash -c 'set -u; . "$1";
  echo "klt=$(type -t klt)"; echo "py=$(type -t klt_python)"; echo "pin=$KLT_PIN"' \
  _ "$here/klt.sh" 2>&1)"; rc=$?
check "exported KLT_NO_FUNCTION source exits 0" 0 "$rc"
lit "exported KLT_NO_FUNCTION warning" "ignoring KLT_NO_FUNCTION inherited from the environment" "$out"
lit "exported KLT_NO_FUNCTION klt facet" "klt=function" "$out"
lit "exported KLT_NO_FUNCTION klt_python facet" "py=function" "$out"
lit "exported KLT_NO_FUNCTION pin" "pin=$pin" "$out"

# edge cases: exported-but-empty and exported 0 are likewise inherited and
# ignored; a caller-local 0 keeps the facets and stays silent.
out="$(KLT_NO_FUNCTION='' bash -c '. "$1"; echo "klt=$(type -t klt)"' _ "$here/klt.sh" 2>&1)"; rc=$?
check "exported empty KLT_NO_FUNCTION exits 0" 0 "$rc"
lit "exported empty KLT_NO_FUNCTION ignored" "klt=function" "$out"
lit "exported empty KLT_NO_FUNCTION warning" "ignoring KLT_NO_FUNCTION" "$out"
out="$(KLT_NO_FUNCTION=0 bash -c '. "$1"; echo "klt=$(type -t klt)"' _ "$here/klt.sh" 2>&1)"; rc=$?
check "exported 0 KLT_NO_FUNCTION exits 0" 0 "$rc"
lit "exported 0 KLT_NO_FUNCTION ignored" "klt=function" "$out"
out="$(bash -c 'set -u; KLT_NO_FUNCTION=0; . "$1"; echo "klt=$(type -t klt)"' \
  _ "$here/klt.sh" 2>&1)"; rc=$?
check "caller-local KLT_NO_FUNCTION=0 exits 0" 0 "$rc"
lit "caller-local 0 keeps facets" "klt=function" "$out"
lit_not "caller-local 0 silent" "ignoring KLT_NO_FUNCTION" "$out"

# the pin resolves from BASH_SOURCE: source from a cwd that is not the repo root.
out="$(cd "$tmp" && bash -c '. "$1"; echo "$KLT_PIN"' _ "$here/klt.sh" 2>&1)"; rc=$?
check "foreign cwd source exits 0" 0 "$rc"
[[ "$out" == "$pin" ]] || { echo "FAIL foreign cwd pin: $out"; fail=1; }

exit "$fail"
