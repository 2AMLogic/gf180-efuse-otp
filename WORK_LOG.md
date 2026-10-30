# Work Log

Chronological record of merged PRs and closed issues. Maintained by the Guide role.

### 2026-10-30

- **PR #65**: sim: add sense-margin batch campaign record
- **Issue #28** (closed): T1 item 9 (testbenches shipped): sense-margin bench, testbench inventory and --attest 9

### 2026-10-28

- **PR #63**: docs: add T1 item 8 characterization report and inventory
- **PR #58**: docs: propose 10 MHz controller clock target as decision 0006

### 2026-10-27

- **PR #56**: docs: record clean curated-deck DRC verdicts in signoff README
- **PR #54**: refactor: generate klt FV requests from runner.py CONFIGS
- **Issue #52** (closed): Single-source the controller parameter sets (runner.py CONFIGS, klt-fv.sh table, 9 request JSONs)
- **Issue #31** (closed): T1 item 3 (DRC clean): klt drc on both partitions, including a route to the EF.* rules
- **PR #51**: layout: make the digital partition DRC-clean via explicit PDN straps and 15 um tap pitch
- **Issue #49** (closed): T1 item 3 (DRC), digital partition: classify the 2525 hits by source and fix or document each
- **PR #42**: sim: add sense-margin bench, testbench inventory and item 9 attestation
- **PR #50**: layout: snap placement and resistor lengths to the rule grid, analog DRC clean
- **Issue #48** (closed): T1 item 3 (DRC), analog partition: grid-snap cell placement in gen_efuse_otp.py to clear 2560 *.ongrid.1 hits
- **PR #47**: verification: record klt functional-verification and multi-corner STA of the routed controller
- **PR #46**: layout: record klt drc results for both partitions (not clean; item 3 stays unmet)
- **PR #44**: layout: route the digital controller with klt place-and-route and attest item 2
- **PR #43**: feat(layout): placed analog layout stream with reproducible generator
- **PR #38**: ci: run controller bench in CI, add README reproduce steps, attest T1 item 10
- **Issue #30** (closed): T1 item 2 (layout, digital): klt place-and-route flow and routed GDS for efuse_otp_ctrl
- **Issue #29** (closed): T1 item 2 (layout, analog): generated GDS for the fuse bitcell, 32x8 array, drivers and sense path
- **Issue #27** (closed): T1 item 10 (repo hygiene): README reproduction steps, controller bench in CI, klt signoff --attest 10
- **PR #39**: feat(design): analog schematics, derived netlist and item 1 analog attestation
- **PR #37**: feat(rtl): commit mapped gf180mcu netlist and attest T1 item 1 (digital)
- **Issue #25** (closed): T1 item 1 (design sources, analog): schematics and derived netlist for the fuse array, program drivers and sense path
- **Issue #26** (closed): T1 item 1 (design sources, digital): klt synthesize efuse_otp_ctrl to a committed gf180mcu gate-level netlist

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
