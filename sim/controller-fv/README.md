# controller-fv

Committed `klt functional-verification` reports for the controller bench
(`verification/`), one per parameter set. They are the cited evidence behind the
controller rows of `measurements/characterization/README.md` (C3, P01, P05, P11,
P12) and are hash-bound in the T1 item 8 attestation.

This README exists because the reports were produced by an **older klt than the
current pin**, so a fresh run does not reproduce the committed envelope. The
difference is a klt report-schema difference, not a result difference.

| | |
|---|---|
| Files | nine `<set>.report.json`: `32x8_min` / `nom` / `max`, `1x8_min` / `nom` / `max`, `32x8_clamp_lo` / `clamp_hi`, `32x8_100MHz_max` |
| Result | 9 sets, `status: pass`, `test_count` / `passed_count` 12/12, `failed_count` / `skipped_count` 0 |
| Produced by | **klt 0.8.0**, `schema_version: 1` |
| Recorded in | `7a1d430` (2026-10-27), while `signoff/klt-pin.txt` was `klayout-tools==0.8.0` (set in `74dd137`, same day) |
| Current pin | `klayout-tools==0.9.2` (since the 2026-11-17 pin bump), which emits `schema_version: 2` |

The 0.9.0 pin bump re-attested items 1/9/10 and moved the item 8 *inventory* to
the 0.9.0 schema; it did not regenerate these reports. Nothing else in the repo
records which klt produced them, which is what this file is for.

## Envelope delta: committed (klt 0.8.0) vs a fresh run (klt 0.9.0)

| Field | Committed (0.8.0) | Fresh run (0.9.0) |
|---|---|---|
| `schema_version` | `1` | `2` |
| `environment.results_xml` | bare absolute path | `{"path": null, "scope": "external"}` |
| `environment.test_log` | bare absolute path | `{"path": null, "scope": "external"}` |
| `environment.build_log` | bare absolute path | `{"path": null, "scope": "external"}` |
| `environment.env` | **absent** | `{}` |
| `environment.tools` | **absent** | `[]` |

`env` and `tools` are **absent** from the committed reports, not `null`: 0.9.0
adds two `environment` keys rather than filling two existing ones.

**Nothing else moves.** Everything that carries the result is identical across
the two schema versions — `status`, all four count fields, every
`tests[].name`, every `tests[].status`, every `tests[].sim_time_ns`,
`hdl_toplevel`, `testbench`, `coverage`, `trace`, and the other seven
`environment` keys (`engine` `icarus`, `engine_version` 13.0, `cocotb_version`
2.1.0, `random_seed`, `source_defines`, `initial_state`, `sdf`). The Icarus and
cocotb pins did not change across the klt bump, so the whole delta is klt's
report envelope. **An envelope diff against a fresh run is expected and is not
a result change.**

The committed log pointers are bare absolute paths that still carry the
`.loom/worktrees/issue-35/` prefix of the worktree that produced them; 0.9.0
drops the pointer (`path: null`, `scope: external`) rather than rewriting it
repo-relative. Neither form resolves to a committed artifact — the logs
(`results_icarus.xml`, `test_icarus.log`, `build_icarus.log`) were never
committed, and this directory holds only the nine reports.

## A regenerated report is never byte-identical to a committed one

`tests[].real_time_s` is per-test wall clock. It moves run to run on the same
machine, the same pin and the same RTL: two consecutive full runs under the
0.9.0 pin produced nine report files that all differed from each other, with
`real_time_s` the only field that moved (70 of the 108 test entries, e.g. `0.0`
-> `0.001`).

So no regeneration can deliver "a fresh run reproduces the committed bytes" —
not under 0.9.0, and not under whatever the pin becomes next. What *is*
reproducible is the result: the test set, every `status`, every `sim_time_ns`
and the 12/12 counts were stable across both runs and across both klt versions.

## Do not regenerate these files in place

All nine are hash-bound evidence in `signoff/attest/item8.envelope.json` — 9 of
its 80 `attestation.checks`, each `role: evidence`, `check: present`, under
`attestation.hash_algorithm: sha256-raw-bytes` — and CI gates that envelope's
freshness (`.github/workflows/ci.yml`, step "Item 8 attestation is current":
`klt signoff --attest 8 ... --check`, exit 3 = stale). Replacing any report
changes its `content_hash`, so regenerating turns CI red unless item 8 is
re-attested in the **same commit** (`signoff/README.md` § "Re-attest item 8").

Whether a tool-version refresh of a cited report counts as replacing a
committed record is an **operator decision, and it has not been taken**:
`CLAUDE.md` holds `sim/` results to be append-only evidence, while
`signoff/README.md`'s pin-bump protocol regenerates other products of the
pinned klt. Until that is ruled on, these nine files stay as they are and this
README records why they differ from a fresh run.

Mechanically the append-only CI check does not reach them —
`scripts/ci/check_sim_append_only.py` matches `^sim/(?:.+/)?records/.+` and this
directory is not under `records/`. That is a gap in the check's coverage, not
permission.

## Comparing against a fresh run

```sh
verification/klt-fv.sh /tmp/fv-compare   # regenerate to a temp dir and compare there
```

**Pass an outdir — it is required.** `verification/klt-fv.sh <outdir>` has no
default destination: an omitted or empty argument prints usage and exits
nonzero before the bench runs, so a no-argument run cannot overwrite the nine
committed reports in place. Diff the fresh reports against the committed ones
with the delta table above in hand, and ignore `tests[].real_time_s`.

## How the above was established

Append-only: do not rewrite these entries; add a new dated one to disagree.

- **2026-11-14, two full `verification/klt-fv.sh` runs to separate temp
  directories under the 0.9.0 pin** (9 sets, `ALL CHECKS PASSED`, 12/12 each):
  established the envelope delta table against the committed reports, that no
  field other than those six differs in any of the nine, and the
  non-reproducibility of `real_time_s` (all nine files differ between the two
  runs; 70 of 108 test entries).
- **2026-11-14, `klt 0.8.0` run of the `32x8_min` request** (emitted with
  `runner.py --emit-klt-requests`, pinned `cocotb==2.1.0` supplied the same way
  `runner.py` does): emits `schema_version: 1` with exactly the ten
  `environment` keys the committed reports carry and bare absolute log paths,
  12/12, with every `tests[].name` and `tests[].sim_time_ns` identical to the
  committed `32x8_min.report.json`. With `git log` showing `7a1d430` as the only
  commit to touch this directory and the pin at that commit reading
  `klayout-tools==0.8.0`, that fixes the producing version.
- **2026-11-14, stdlib `hashlib` recomputation of the nine committed files**:
  all nine match their `content_hash` in `signoff/attest/item8.envelope.json`
  today, and that envelope's own `provenance.klt_version` is `0.9.0` — it was
  re-attested under the current pin over the 0.8.0 report bytes.
- **2026-11-14, `klt signoff --attest 8 ... --check` under the pinned klt**:
  exit 0, `status: match`. `signoff/attest/item8.json` names the nine report
  paths explicitly and contains no globs, so adding this README does not change
  the envelope.
