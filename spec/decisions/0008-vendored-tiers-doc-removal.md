# 0008 — Remove the vendored design-evidence tiers doc

Status: accepted. Date: 2026-11-23. Filed through #131: the operator ruling
of 2026-11-23 (attended `/fleet:decide` session, round 20261121-r19, q103)
reverses the earlier decision to vendor the tiers doc. This record cites the
ruling, states the reversal, and changes no parameter, signoff criterion or
item disposition.

## Decision

`signoff/design-evidence-tiers.md` — the vendored copy of the tiers doc that
`--tiers-doc` pointed the grader at — is deleted, and every caller drops the
`--tiers-doc` override. The pinned klayout-tools release alone selects the
checklist: `klt signoff` grades against the design-evidence tiers doc shipped
inside the pinned release (`signoff/klt-pin.txt`, `klayout-tools==0.9.2`;
[`docs/design-evidence-tiers.md`](https://github.com/2AMLogic/klayout-tools/blob/v0.9.2/docs/design-evidence-tiers.md)
at the tag). CI's "Re-grade signoff record" `cmp` of a fresh pinned run
against the committed record is kept; together with the record's
`source_doc_content_hash` it is what catches a checklist change at a pin
bump.

## Measurements

The signoff record was regenerated once for this change with the pinned klt
(no `--tiers-doc`, exit 3 as before). The committed record's diff is a single
line: `source_doc` moves from `signoff/design-evidence-tiers.md` to
`docs/design-evidence-tiers.md` (klt's built-in label for its shipped doc —
a source-relative path, not a path in this repo). `source_doc_content_hash`,
every item verdict, every count and the `build` block are unchanged, so the
ruling's stop condition (a verdict or tier change) did not trigger. Item 10
was re-attested because `README.md` and `.github/workflows/ci.yml` (hygiene
inputs) changed in the same PR, and item 8 because the record it hashes
changed; neither re-attest touched an inventory sha256, so the second
regeneration was byte-identical (the convergence `signoff/README.md`
describes).

## Background

The vendoring was deliberate: `signoff/README.md` kept a byte-identical copy
of the pinned wheel's `klayout_tools/data/design-evidence-tiers.md` "so the
record does not move when an installed klt bundles a different doc". The
ruling removes it: the record is only ever produced by the pinned release
(the regenerate command and CI both resolve klt through `signoff/klt-pin.txt`),
a doc change cannot pass silently either way (`source_doc_content_hash`, plus
CI's re-grade `cmp` on `build.version`/`build.git_commit` movement), and the
pin bump loses its manual "replace the copy" step — the exact mismatch the
copy guarded against.

## Consequences

- The checklist is selected by `signoff/klt-pin.txt` alone; a pin bump is
  "change the pin, regenerate, re-attest", with no doc copy to replace.
- The record's `source_doc` value is klt's own source-relative label, not a
  path in this repo; the hash beside it identifies the doc content.
- All ratified spec criteria, item verdicts and dispositions are unchanged.
