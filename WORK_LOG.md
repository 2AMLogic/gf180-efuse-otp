# Work Log

Chronological record of merged PRs and closed issues. Maintained by the Guide role.

### 2026-10-23

- **Issue #14** (closed): rtl: synchronous OTP controller with arm-after-reset protection and cocotb bench (T1 items 1, 9, digital partition)
- **PR #22**: fix(sim): drop unused --backend option from program-select run.sh
- **PR #19**: docs(sim): record searched sources for nfet_06v0 voltage limit
- **Issue #20** (closed): Remove dead --backend flag from sim/program-select/run.sh (parsed, never used, contradicts batch-only header)
- **Issue #18** (closed): Cite the PDK numeric voltage limit for nfet_06v0 (follow-on from PR #17)
- **PR #17**: feat(sim): program-select width sweep bench, 60 um passes all PVT points
- **PR #16**: feat(rtl): add eFuse OTP controller with arm-after-reset and cocotb bench
- **Issue #15** (closed): sim: size the nfet_06v0 program-select device for >= 10 mA across the decision-0005 corner set (T1 items 1, 5 groundwork, analog partition)

### 2026-10-21

- **PR #11**: Bump Repo Skills 0.24.3 -> 0.24.7

### 2026-10-20

- **PR #6**: ci: add PDK-free harness workflow and committed signoff record
- **Issue #5** (closed): T1 item 10: add a block manifest, a committed signoff record and a PDK-free CI that keeps evidence formats valid

### 2026-10-17

- **PR #8**: docs: ratify eFuse OTP target spec with PDK survey and decision records
- **PR #7**: feat(sim): pin gf180mcu PDK, add revision-checking resolver and smoke record
- **Issue #4** (closed): T1 item 9: pin gf180mcu (open_pdks f6eeac7 via ciel) with a revision-checking resolver and a committed smoke simulation
- **Issue #2** (closed): Draft and ratify the target spec
- **PR #1**: chore(loom): Install Loom 0.19.1181
