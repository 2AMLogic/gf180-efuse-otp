#!/usr/bin/env bash
# Self-test for klt.sh: the uvx-absent preflight (exit 2, message), the [yield]
# extras splice, klt()/klt_python() argv passthrough and KLT_ARGV through a fake
# uvx, the pin read exactly once and actually exported (the declare -x
# attribute, not mere set-ness, observed with any inherited exported KLT_PIN
# scrubbed from the probe's environment), the --no-function source argument
# skipping the function facets (no klt()/klt_python(): the sim benches keep
# their bare host-klt calls) while every inherited KLT_NO_FUNCTION shape -- a
# plain export, an export reassigned sourcing-locally, a declare -ix export --
# stays ignored, the no-caller-passes-it-as-$1 invariant (with a negative
# control), and pin resolution from a foreign cwd (BASH_SOURCE, not cwd).
# Modelled on sim/lib/test_pdk_env.sh.
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
# [[ -n ${KLT_PIN+x} ]] is true for any set variable, exported or not). The
# probe scrubs an inherited exported KLT_PIN from its environment so the
# attribute observed is klt.sh's own export, not the invoking shell's:
# klt.sh's documented usage (". signoff/klt.sh") is exactly what leaves
# KLT_PIN exported in the shell that then runs this suite.
out="$(env -u KLT_PIN bash -c '. "$1"; echo "pin=$KLT_PIN"; echo "argv=$KLT_ARGV";
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

# the opt-out is a source-time argument: ". klt.sh --no-function" defines no
# function facets; pin and extras still defined.
out="$(PATH="$fb:$PATH" bash -c '. "$1" --no-function;
  echo "klt=$(type -t klt)"; echo "py=$(type -t klt_python)"; echo "pin=$KLT_PIN"; echo "yield=${KLT_YIELD[*]}"' \
  _ "$here/klt.sh" 2>&1)"; rc=$?
check "--no-function source exits 0" 0 "$rc"
lit_not "klt defined despite --no-function" "klt=function" "$out"
lit_not "klt_python defined despite --no-function" "py=function" "$out"
lit "--no-function pin" "pin=$pin" "$out"
lit "--no-function yield" "yield=uvx --from klayout-tools[yield]==$version klt" "$out"

# a source argument other than --no-function (and no argument at all) keeps
# both facets.
out="$(PATH="$fb:$PATH" bash -c '. "$1" --other-argument;
  echo "klt=$(type -t klt)"; echo "py=$(type -t klt_python)"' \
  _ "$here/klt.sh" 2>&1)"; rc=$?
check "non-opt-out source argument exits 0" 0 "$rc"
lit "non-opt-out argument klt facet" "klt=function" "$out"
lit "non-opt-out argument klt_python facet" "py=function" "$out"
out="$(bash -c '. "$1"; echo "klt=$(type -t klt)"; echo "py=$(type -t klt_python)"' \
  _ "$here/klt.sh" 2>&1)"; rc=$?
check "plain source exits 0" 0 "$rc"
lit "plain source klt facet" "klt=function" "$out"
lit "plain source klt_python facet" "py=function" "$out"

# issue #225's two shapes cannot take the script off the pin: the environment
# variable path is gone, so an exported KLT_NO_FUNCTION reassigned
# sourcing-locally (shape 1), a declare -ix export (shape 2), and a plain
# inherited export of any value (empty, 0, 1) all leave the facets defined,
# silently -- an inherited exported variable never removes the pinned
# functions (the #200 property).
out="$(KLT_NO_FUNCTION=0 bash -c 'set -euo pipefail; KLT_NO_FUNCTION=1; . "$1";
  echo "klt=$(type -t klt)"; echo "py=$(type -t klt_python)"; echo "pin=$KLT_PIN"' \
  _ "$here/klt.sh" 2>&1)"; rc=$?
check "shape 1 (exported, reassigned local) exits 0" 0 "$rc"
lit "shape 1 klt facet" "klt=function" "$out"
lit "shape 1 klt_python facet" "py=function" "$out"
lit "shape 1 pin" "pin=$pin" "$out"
lit_not "shape 1 silent" "ignoring KLT_NO_FUNCTION" "$out"
out="$(bash -c 'declare -ix KLT_NO_FUNCTION=1; set -u; . "$1";
  echo "klt=$(type -t klt)"; echo "py=$(type -t klt_python)"' \
  _ "$here/klt.sh" 2>&1)"; rc=$?
check "shape 2 (declare -ix) exits 0" 0 "$rc"
lit "shape 2 klt facet" "klt=function" "$out"
lit "shape 2 klt_python facet" "py=function" "$out"
out="$(KLT_NO_FUNCTION=1 bash -c 'set -u; . "$1";
  echo "klt=$(type -t klt)"; echo "py=$(type -t klt_python)"; echo "pin=$KLT_PIN"' \
  _ "$here/klt.sh" 2>&1)"; rc=$?
check "exported KLT_NO_FUNCTION source exits 0" 0 "$rc"
lit "exported KLT_NO_FUNCTION klt facet" "klt=function" "$out"
lit "exported KLT_NO_FUNCTION klt_python facet" "py=function" "$out"
lit "exported KLT_NO_FUNCTION pin" "pin=$pin" "$out"
out="$(KLT_NO_FUNCTION='' bash -c '. "$1"; echo "klt=$(type -t klt)"' _ "$here/klt.sh" 2>&1)"; rc=$?
check "exported empty KLT_NO_FUNCTION exits 0" 0 "$rc"
lit "exported empty KLT_NO_FUNCTION ignored" "klt=function" "$out"
out="$(KLT_NO_FUNCTION=0 bash -c '. "$1"; echo "klt=$(type -t klt)"' _ "$here/klt.sh" 2>&1)"; rc=$?
check "exported 0 KLT_NO_FUNCTION exits 0" 0 "$rc"
lit "exported 0 KLT_NO_FUNCTION ignored" "klt=function" "$out"

# the pin resolves from BASH_SOURCE: source from a cwd that is not the repo root.
out="$(cd "$tmp" && bash -c '. "$1"; echo "$KLT_PIN"' _ "$here/klt.sh" 2>&1)"; rc=$?
check "foreign cwd source exits 0" 0 "$rc"
[[ "$out" == "$pin" ]] || { echo "FAIL foreign cwd pin: $out"; fail=1; }

# the "no caller passes --no-function as its own first parameter" claim in
# klt.sh's header (the opt-out is read from $1, so a caller's own first
# argument would silently drop the pin when it sources without an argument)
# is a checked invariant, not just a comment. A caller is any shell file with
# a source line naming signoff/klt.sh (klt.sh, this test and docs excluded);
# it violates the invariant when a non-comment line other than a klt.sh source
# line mentions --no-function (a case arm, a [[ $1 == ... ]] test, a getopts
# loop). The explicit ". \"$repo/signoff/klt.sh\" --no-function" source line
# is the sanctioned opt-out and is not flagged.
src_re='^[[:space:]]*(\.|source)[[:space:]].*signoff/klt\.sh'
list_callers() { # root -> files (relative) with a klt.sh source line
  local f
  while IFS= read -r f; do
    case "$f" in signoff/klt.sh|signoff/test-klt.sh) continue;; esac
    grep -qE -- "$src_re" "$1/$f" && echo "$f"
  done < <(cd "$1" && find . \( -name .git -o -name .loom -o -name node_modules \) -prune \
             -o -type f -name '*.sh' -print | sed 's|^\./||' | sort)
}
scan_callers() { # root -> prints "file:line" for each own --no-function use
  local f
  while IFS= read -r f; do
    grep -nE -- '--no-function' "$1/$f" | grep -vE -- '^[0-9]+:[[:space:]]*#' \
      | grep -vE -- "^[0-9]+:${src_re#^}" | sed "s|^|$f:|"
  done < <(list_callers "$1")
}
root="$(cd "$here/.." && pwd)"
callers="$(list_callers "$root")"
lit "callers enumerated (non-vacuous): sense-mc opt-out caller" "sim/sense-mc/run.sh" "$callers"
lit "callers enumerated: a bare-source caller" "layout/drc.sh" "$callers"
out="$(scan_callers "$root")"
[[ -z "$out" ]] && echo "PASS no caller handles --no-function itself" \
  || { echo "FAIL caller handles --no-function itself: $out"; fail=1; }
# negative control: a fixture tree whose caller handles --no-function (case
# arm, and a test on $1) while sourcing bare must be flagged, alongside a
# sanctioned explicit opt-out (both path forms) and a comment, which must not.
fx="$tmp/fx"; mkdir -p "$fx/signoff" "$fx/a" "$fx/b"
cp "$here/klt.sh" "$fx/signoff/klt.sh"
printf '%s\n' '. "$root/signoff/klt.sh"' 'case "$1" in --no-function) x=1;; esac' > "$fx/a/bad-case.sh"
printf '%s\n' '. signoff/klt.sh' '[[ "${1:-}" == --no-function ]] && x=1' > "$fx/a/bad-test.sh"
printf '%s\n' '# the --no-function source argument' '. "$repo/signoff/klt.sh" --no-function' > "$fx/b/ok-optout.sh"
printf '%s\n' '. "$root/signoff/klt.sh" --no-function' > "$fx/b/ok-root.sh"
out="$(scan_callers "$fx")"
lit "negative control flags case-arm caller" "a/bad-case.sh:2:" "$out"
lit "negative control flags \$1-test caller" "a/bad-test.sh:2:" "$out"
lit_not "explicit opt-out (repo form) not flagged" "ok-optout.sh" "$out"
lit_not "explicit opt-out (root form) not flagged" "ok-root.sh" "$out"

exit "$fail"
