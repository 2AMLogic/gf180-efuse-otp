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
#   klt_python()   python from the pinned environment (one call site runs
#                  python, not klt, to import the pinned klayout module)
#   KLT_ARGV       the pin as a ready-made command string
#                  ("uvx --from <pin> klt") for argv consumed across a process
#                  boundary (layout/gen_efuse_otp.py --klt)
#   KLT_YIELD      the pin with the [yield] extra spliced in, as an array --
#                  "uvx --from klayout-tools[yield]==<pin version> klt" -- for
#                  the klt yield grading
# Both functions are defined unconditionally: this file reads neither the
# environment nor its positional parameters, so no inherited variable or
# caller argument can switch a signoff script off the pinned klt. The one
# caller that wants its own bare klt (the sim/* benches, which call a host
# klt through sim/lib/pdk_env.sh) still gets KLT_PIN and KLT_YIELD, and
# unsets the functions itself right after sourcing: unset -f klt klt_python.
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
klt() { uvx --from "$KLT_PIN" klt "$@"; }
klt_python() { uvx --from "$KLT_PIN" python "$@"; }
unset _klt_root
