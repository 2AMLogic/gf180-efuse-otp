# 0007 — DRC tool survey reconciliation

Status: accepted. Date: 2026-11-21. Filed through #318: §1.3's curated
inventory and native deck execution bullets were measured at the survey
revision and never re-derived after the klt pin moved. This record
re-derives both, restates the two bullets, and changes no parameter,
signoff criterion or item disposition.

## Decision

`spec/efuse-otp.md` §1.3 bullets 1 and 3 are restated per the measurements
below. The primitive result (bullet 2) keeps its own input and count: the
pinned PDK's original `efuse.gds`, 64 violations, all `*.ongrid.1`. All
ratified signoff criteria stand, and the item 3 disposition (3.analog and
3.digital uncited, #60) is unchanged.

## Measurements

PDK: `open_pdks f6eeac7dad085ffcc829ccfd721f7b4ce39edcf7`, the §1 citation
baseline, unchanged; `layout/drc.sh --check` ran against this tree.

| | survey revision | current pin |
|---|---|---|
| klt | `0.7.1.dev1754+g81ac4d3915c1` | `klayout-tools==0.9.2` (`signoff/klt-pin.txt`) |
| observed | 2026-10-17 (PR #8 survey) | 2026-11-21, `4c155df` |
| `klt drc --deck gf180mcu --list-rules --format json` | 94 rules | 126 rules |
| rule IDs starting `EF.` | 0 | 0 |
| rules with `scope == "EF"` | 0 | 7 |

Commands. Survey revision, in a klayout-tools checkout at
`81ac4d3915c1ae787ba66c26b74a55a31b277ed2`:
`uv run --no-sync --with . klt drc --deck gf180mcu --list-rules --format json`.
Current pin, at the repo root: `. signoff/klt.sh`, then
`klt drc --deck gf180mcu --list-rules --format json`. Both listings checked
with `jq '[.rules|length, (map(select(.id|startswith("EF.")))|length),
(map(select(.scope=="EF"))|length)]'`: `[94,0,0]` and `[126,0,7]`.

The 94-to-126 change is 32 added rule IDs and zero removals (sorted-ID
comparison across the two listings). Additions by group: nine guard-ring-mark
separation rules (`comp`, `metal1`–`metal5`, `metaltop`, `nwell`, `poly2`,
each `+ separation.guard_ring_mk.1`), seven ESD geometry rules, seven
EF-scope rules (below), four medium-voltage rules (`mvsd.width.1`,
`mvsd.separation.dnwell.1`, `mvsd.ongrid.1`, `mvpsd.ongrid.1`), two
`dualgate` rules, two `comp.tap_distance.*` rules and
`ldmos_xtor.enclosing.mvpsd.1`. None is named `EF.*`.

Curated EF scope is not foundry rule names. The seven EF-scope additions are
separation and enclosure checks named after their layers: `efuse_mk.space.1`,
`efuse_mk.enclosing.lvs_source.1`, and
`plfuse.separation.{comp,nplus,esd,sab,resistor}.1`. Zero curated rule IDs
start with `EF.` at either revision: the exact-value foundry rules keep their
`EF.*` names only in the PDK decks (`efuse.rb`, `gf180mcu.drc`). A prefix
count alone therefore understates curated EF coverage — the survey's
"zero `EF.*` rules" was true of names and remains so, but it is not a
coverage statement.

Native deck execution (bullet 3). `layout/drc.sh` does not rely on deck
discovery: it passes the PDK's main deck explicitly — `--engine klayout
--deck gf180mcu --pdk <variant> --deck-file
pdk/<variant>/libs.tech/klayout/tech/drc/gf180mcu.drc` with
`--deck-var variant=<variant> --deck-var decks=all --deck-var threads=1`
and `--min-klayout-version 0.30.9` — array variant `gf180mcuC`, controller
variant `gf180mcuD`. `layout/drc.sh --check` (2026-11-21, `4c155df`) matched
the committed input and deck hashes for all seven reports. Both native
reports committed by PR #313 — `layout/drc-array.native.report.json`
(gf180mcuC, 253 violations) and `layout/drc-ctrl.native.report.json`
(gf180mcuD, 9 violations) — list all 27 `EF.*` IDs in
`coverage.rules_checked`, record zero EF entries in `rule_counts`, and
report overall status `violations`. This establishes explicit `--deck-file`
execution at 0.9.2. Whether klt can discover the native deck without
`--deck-file` is a separate claim; this record does not make it. The old
bullet's error quote ("no PDK-native klayout DRC deck script found for this
PDK variant") was a discovery observation at the survey revision,
2026-10-17.

## Consequences

- §1.3 bullets 1 and 3 now cite this record; bullet 2 is untouched.
- The §1.3 friction items stand: the curated deck still carries no
  exact-value `EF.*` width/length rules at 0.9.2 (0 of 126 IDs).
- PR #313's drift note ("the curated inventory now has 126 rules") is
  resolved: the number and its derivation are on record here.
- Automatic native-deck discovery remains untested. No runner or tool
  change is made or required by this record.
