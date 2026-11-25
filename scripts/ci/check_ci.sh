#!/usr/bin/env bash
# Single source of the check:ci hermetic term list (#267).
#
# package.json scripts["check:ci"] and the harness job in
# .github/workflows/ci.yml both call this script, so the local gate and CI run
# the identical list by construction; README.md points here instead of
# enumerating the terms. Each check prints a "==> <name>" line before it runs,
# so a failure names its check as the last such line in the log.
#
# Run from the repository root. Hermetic: nothing here needs an EDA tool, the
# PDK or a diff base -- those stay as named steps of ci.yml's harness job.
set -euo pipefail

ran=()
run() {
  echo "==> $1"
  ran+=("$1")
  shift
  "$@"
}

run "checker self-tests" bash -c "cd scripts/ci && python3 -I -m unittest discover -s . -p 'test_*.py' -v"
run "evidence format" python3 scripts/ci/check_evidence_format.py
run "attestation pin" python3 scripts/ci/check_attest_pins.py
run "report input hashes" python3 scripts/ci/check_report_inputs.py
run "item 6 spec binding" signoff/check-item6-digital.sh
run "PVT grid binding" signoff/check-pvt-grid.sh
run "pdk_env self-test" sim/lib/test_pdk_env.sh
run "klt helper self-test" signoff/test-klt.sh
run "bench_record load_reports self-test" python3 -I sim/lib/test_bench_record.py
run "program-select summarize self-test" python3 -I sim/program-select/test_summarize.py
run "sense-margin summarize self-test" python3 -I sim/sense-margin/test_summarize.py
run "sense-breakeven summarize self-test" python3 -I sim/sense-breakeven/test_summarize.py

printf -v checks '%s, ' "${ran[@]}"
echo "check:ci OK -- hermetic checks only: ${checks%, }. This does NOT run the CI steps that need an EDA tool, the PDK or a diff base (verification/run.sh, rtl/synth.sh, the klt signoff steps, check_sim_append_only.py), so a green check:ci is not a prediction that CI will pass."
