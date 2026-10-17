# signoff

The block's verdict of record against the klayout-tools evidence tiers.

| File | Role |
|---|---|
| `block-manifest.json` | Block name, kind (`mixed-signal`) and the `evidence` map (empty until evidence lands). |
| `block-manifest.signoff.json` | Committed `klt signoff --manifest` output: the verdict of record. Today every T1 row, for both partitions, is `unmet` / `no_evidence`. |
| `klt-pin.txt` | The single place the grader version is pinned. CI installs `$(cat signoff/klt-pin.txt)`. |
| `design-evidence-tiers.md` | Copy of the tiers doc shipped with the pinned klt (`klayout-tools==0.7.0`, `klayout_tools/data/design-evidence-tiers.md`), so the record does not move when an installed klt bundles a different doc. |

## Regenerate the record

Always with the pinned release, never a host-installed `klt`:

```sh
uvx --from "$(cat signoff/klt-pin.txt)" klt signoff \
  --manifest signoff/block-manifest.json \
  --tiers-doc signoff/design-evidence-tiers.md \
  --format json > signoff/block-manifest.signoff.json
```

Exit 3 means the report was produced with items unmet; that is the expected
state. Any other non-zero exit is a failure.

To bump the pin: change `klt-pin.txt`, replace `design-evidence-tiers.md` with
the copy shipped in the new release, regenerate, and commit all three together.

## What CI does and does not check

`.github/workflows/ci.yml` installs only Python and the pinned klt (no PDK,
ngspice, xschem or klayout). It checks that:

- the checker self-tests still reject seeded-bad input;
- each evidence directory has a `README.md`, and any `sim/**/records/*.json`
  has the required fields, a PDK revision, and repo-relative paths only
  (vacuously true while there are no records);
- files under `sim/**/records/` are only added, never modified, deleted or renamed;
- re-grading the manifest reproduces the committed record byte for byte.

**CI does not check that any evidence is correct.** It checks formats,
append-only history, and that the record reproduces.
