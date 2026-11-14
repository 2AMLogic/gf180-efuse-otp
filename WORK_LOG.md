# Work Log

Chronological record of merged PRs and closed issues. Maintained by the Guide role.

### 2026-11-14

- **PR #152**: docs: drop the retyped tool-version column from the testbench inventory
- **Issue #164** (closed): check_evidence_format.py grades zero sim records: the glob misses records/<stamp>/record.json and reports a vacuous pass
- **Issue #163** (closed): Re-evaluate T1 item 3's EF coverage disclosure: the pinned klt deck gained an EF scope and now checks five eFuse-layer rules
- **Issue #147** (closed): Remove the retyped tool versions from sim/README.md's testbench inventory: the analog rows say klt 0.8.0, the attested item 9 inventory pins 0.9.0

### 2026-11-13

- **PR #143**: refactor(sense-mc): derive record.json's run constants from run.sh instead of retyping them
- **PR #142**: fix(sense-mc): drop the non-resolving-latch reason, take variant strings from bench_record
- **PR #141**: docs(layout): stop the "not claimed" bullet from restating DRC status
- **PR #138**: refactor(signoff): produce both item 2 envelopes with klt signoff --attest 2
- **PR #136**: docs: drop the Yosys version gate rtl/synth.sh never had
- **PR #135**: docs(corner-verification): state 45 corners per request, supplies paired not crossed
- **PR #132**: fix(signoff): re-pin 1.analog, re-attest item 8, and guard it in CI
- **PR #127**: docs(signoff): state each re-attest procedure and the item 1 pin rule once
- **PR #126**: build: wire check:ci to the repo's hermetic checks, drop three always-green stubs
- **PR #123**: refactor(sim): hoist record-provenance boilerplate into sim/lib/bench_record.py
- **PR #122**: refactor: drop dead records/ cleanup loop from sim/cold-start.sh
- **Issue #140** (closed): Stop retyping sim/sense-mc/run.sh's run constants in summarize.py: the decision limit, fuse values, control references and corner count reach record.json as separate literals
- **Issue #139** (closed): layout/README.md 'What is not claimed' says neither partition is DRC clean; the DRC section below it reports both clean
- **Issue #137** (closed): Remove two stale provenance statements from sim/sense-mc: the 'comparator never resolves' reason in run.sh and the hand-typed PDK variant strings in summarize.py
- **Issue #134** (closed): Correct the 135-corner statements for sim/corner-verification: each request runs 45 corners (supplies paired, not crossed)
- **Issue #129** (closed): Repair the stale 1.analog manifest pin and the drifted record hash in the item 8 envelope
- **Issue #128** (closed): Remove the documented Yosys version gate that rtl/synth.sh never had, and the leftover 'cold start needs Yosys' statements
- **Issue #125** (closed): Remove the stale duplicate 'Re-attest item 8' section and the contradicted item 1 pin instructions from signoff/README.md
- **Issue #124** (closed): Replace the four always-green placeholder scripts in package.json with one real check:ci
- **Issue #117** (closed): Hoist duplicated record-provenance boilerplate from sim/*/summarize.py into sim/lib
- **Issue #115** (closed): Remove dead dry-run cleanup in sim/cold-start.sh: program-select dry runs no longer write under records/
- **PR #113**: refactor(sim): hoist batch dry-run and submit blocks into pdk_env.sh
- **Issue #112** (closed): Hoist duplicated klt batch dry-run and submit blocks from sim/*/run.sh into sim/lib
- **PR #109**: refactor(sim): use shared bench helpers in program-select and sense-margin, re-attest item 9
- **PR #107**: refactor(sim): hoist shared bench boilerplate into sim/lib
- **Issue #108** (closed): Migrate sim/program-select and sim/sense-margin run.sh to shared bench helpers
- **Issue #106** (closed): Hoist duplicated run.sh boilerplate (arg parse, sub(), record dir) into sim/lib

### 2026-11-12

- **PR #105**: Bump Repo Skills 0.25.10 -> 0.26.1

### 2026-11-10

- **PR #100**: docs: cite graded sense records and attest characterization report (item 8)
- **Issue #62** (closed): T1 item 8 (characterization report): per-ratified-row report with controller Fmax/area/power, attested with --attest 8

### 2026-11-09

- **PR #98**: sim: declare margin_v limit in sense-margin campaign; item 5 analog grades met
- **PR #97**: refactor(sim): share the gf180mcuC/D fleet-image check via pdk_fleet_check
- **PR #96**: chore(verification): drop dead Yosys version gate from controller bench runner
- **PR #95**: fix(design): widen column driver to 3x100um to clear 10 mA at the binding corner
- **PR #93**: docs(signoff): repoint P10 evidence to post-#85 records, restate P10 gap
- **Issue #88** (closed): Re-cite sense row P10 for items 5 and 6 (analog) to the post-#85 comparator records
- **Issue #68** (closed): Dedupe fleet-image PDK variant check and report fold across sim benches
- **Issue #40** (closed): Remove rtl/synth.sh: superseded by regen-gl.sh latch check, plus dead Yosys gate in cocotb runner
- **Issue #34** (closed): T1 item 5 (corner verification, analog): klt sim envelopes for program current and sense margin across decision-0005 PVT

### 2026-11-07

- **PR #90**: chore: bump Repo Skills 0.25.1 -> 0.25.10

### 2026-11-06

- **PR #87**: refactor: generate comparator probe decks from one template
- **Issue #83** (closed): Consolidate sense-margin probe decks: 10 near-identical 126-line netlists differ by 1-2 lines

### 2026-11-05

- **PR #85**: fix: widen comparator input pair to 8u/2.24u for intact-edge decision yield
- **PR #84**: fix: enlarge comparator input pair to cut offset-driven wrong decisions
- **PR #82**: build(signoff): bump klt pin to 0.9.0 and re-attest; item 8 inventory moves to new schema
- **Issue #77** (closed): Sense comparator does not resolve a decision for resistive fuses; comparator offset unevidenced
- **PR #80**: feat(sim): re-run sense-mc campaign on resized comparator, record decision yield
- **PR #79**: fix: size comparator latch to out-pull input pair, resolve sense bench timestep
- **PR #78**: feat: sense-path Monte Carlo campaign and item 6 evidence (analog yield, digital not-applicable)
- **Issue #36** (closed): T1 item 6 (Monte Carlo): klt yield on sense margin, and the controller's not-applicable statement
- **PR #75**: docs: refresh README status to match committed artifacts
- **Issue #74** (closed): Refresh README status line: sense path, DRC and controller routing exist

### 2026-11-01

- **PR #70**: Bump Repo Skills 0.24.7 -> 0.25.1

### 2026-10-30

- **PR #67**: sim: program-current corner verification on the real driver path; item 5 analog regraded unmet
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
