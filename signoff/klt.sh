#!/usr/bin/env bash
# The single sourced definition of how this repo reaches its pinned klt
# (signoff/klt-pin.txt, through uvx --from). The pin file is the one place the
# grader version is pinned; this file is the one place the mechanism for
# reaching it is defined. Source it instead of hand-copying the incantation:
#
#   . signoff/klt.sh                  # cwd is the repo root
#   . "$root/signoff/klt.sh"          # any cwd: the pin path resolves from
#                                     # BASH_SOURCE, not $PWD
#
# Reads the pin exactly once, preflights uvx (exit 2 if absent, before any
# caller setup), and defines the facets the call sites need:
#   KLT_PIN        the raw pin string ("klayout-tools==X"), exported -- the
#                  recorded provenance value (sim/sense-mc passes it on as
#                  --klt-pin) and what every other facet is built from
#   klt()          the pinned klt as a command
#   klt_python()   python from the pinned environment (two call sites run
#                  python, not klt, to reach klayout_tools internals)
#   KLT_ARGV       the pin as a ready-made command string
#                  ("uvx --from <pin> klt") for argv consumed across a process
#                  boundary (layout/gen_efuse_otp.py --klt)
#   KLT_YIELD      the pin with the [yield] extra spliced in, as an array --
#                  "uvx --from klayout-tools[yield]==<pin version> klt" -- for
#                  the klt yield grading
# Source with the --no-function argument -- ". signoff/klt.sh --no-function"
# -- to skip the klt() and klt_python() facets: the sim/* benches call a bare
# host klt (sim/lib/pdk_env.sh) and must keep doing so, but still need KLT_PIN
# and KLT_YIELD. The opt-out is an argument, not an environment variable: a
# source-time argument cannot be inherited, so no environment state can switch
# a signoff script off the pinned klt. It is read from $1: sourcing with an
# argument sets the positional parameters for the sourced file alone (bash
# restores the caller's afterwards); sourced without an argument, $1 is the
# caller's own first parameter, and no caller passes --no-function as one.
#
# verification/run.sh keeps its own inline preflight by design: it is the
# exemplar this message was taken from, and it is a content-hashed attestation
# input (signoff/attest/item9.envelope.json), so editing it would force a
# re-attest cascade for no dedupe gain. Self-test: signoff/test-klt.sh.

_klt_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v uvx >/dev/null 2>&1 || { echo "uvx not found; the pinned klt in signoff/klt-pin.txt is reached through it" >&2; exit 2; }
[[ -r "$_klt_root/signoff/klt-pin.txt" ]] || { echo "signoff/klt.sh: pin file missing: $_klt_root/signoff/klt-pin.txt" >&2; exit 2; }
KLT_PIN="$(cat "$_klt_root/signoff/klt-pin.txt")"
export KLT_PIN
KLT_ARGV="uvx --from $KLT_PIN klt"
KLT_YIELD=(uvx --from "${KLT_PIN%%==*}[yield]==${KLT_PIN##*==}" klt)
# The opt-out is the source-time argument --no-function, not an environment
# variable: an argument is passed to this file's execution alone and cannot be
# inherited, so an exported KLT_NO_FUNCTION of any value leaves both facets
# defined. No attribute introspection is needed -- the previous declare -p
# prefix test misjudged an exported variable reassigned sourcing-locally
# (it keeps the -x attribute) and a declare -ix export (not a prefix match),
# and its ${var@a} alternative needs bash 5.1+.
_klt_nofunc=0
if [[ "${1-}" == "--no-function" ]]; then _klt_nofunc=1; fi
if [[ "$_klt_nofunc" != 1 ]]; then
  klt() { uvx --from "$KLT_PIN" klt "$@"; }
  klt_python() { uvx --from "$KLT_PIN" python "$@"; }
fi
unset _klt_root _klt_nofunc
