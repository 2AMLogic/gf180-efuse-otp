# Work Log

Chronological record of merged PRs and closed issues. Maintained by the Guide role.

### 2026-11-16

- **PR #239**: test: pin signoff checker failure modes with seeded-bad-input self-tests
- **Issue #214** (closed): Neither signoff bash checker has a self-test: check-pvt-grid.sh and check-item6-digital.sh can go vacuous with CI green
- **PR #236**: fix(signoff): opt out of the klt facets with a --no-function source argument
- **PR #234**: ci: run the bench_record load_reports self-test in the harness job
- **Issue #231** (closed): check:ci's sim/lib/test_bench_record.py term has no ci.yml step: the gap #217 closed reopened one merge later
- **Issue #225** (closed): signoff/klt.sh: the declare -x proxy for 'inherited' has two residual shapes where the sourcing-local contract is not honored
- **PR #232**: ci: refuse unsupported hash_algorithm in attestation pin check
- **PR #230**: ci: run every uncovered check:ci term in the harness job
- **PR #228**: fix(rtl): broaden the latch-gate glob to catch fine-grain $_DLATCHSR_* cells
- **PR #227**: signoff: pin layout/lvs-ctrl.report.json in the item 8 attestation
- **PR #220**: docs: add the klt helper self-test to README's check:ci pre-flight list
- **PR #216**: refactor(sim): single-source the corner benches' refuse-a-partial-set report loading
- **PR #212**: fix: gate the signoff klt opt-out on the export attribute, assert the export
- **Issue #222** (closed): Item 8 envelope does not hash layout/lvs-ctrl.report.json
- **Issue #218** (closed): README's check:ci enumeration omits the klt helper self-test (signoff/test-klt.sh)
- **Issue #217** (closed): The sim summarizer self-tests never run in GitHub CI: only the local npm check:ci gate invokes them, so they can go red with CI green
- **Issue #211** (closed): check_attest_pins.py never reads attestation.hash_algorithm, so a klt hash-kind change reports 87 false 'drift' lines with unfixable remediation
- **Issue #208** (closed): Hoist the absent/hollow report guard from sim/*/summarize.py into bench_record: two copies drifted, a third bench has none
- **Issue #200** (closed): signoff/klt.sh: KLT_NO_FUNCTION is honored from the ambient environment, and its self-test asserts 'set' where it says 'exported'
- **Issue #193** (closed): rtl/synth.ys latch assertion does not cover the fine-grain $_DLATCHSR_* cell type
- **PR #219**: ci(rtl): add a committed negative control proving the latch gate can fail
- **PR #198**: check:ci: add attestation-envelope pin pre-flight
- **Issue #204** (closed): The latch gate has no committed negative control: a typo'd select pattern would make CI's only latch check silently permanent-green
- **Issue #185** (closed): check:ci has no attestation-drift pre-flight: editing any item-10 hygiene artifact fails CI two steps deep with a green local gate
- **PR #215**: test: assert engine_versions provenance in the program-select summarizer self-test
- **PR #209**: ci: run the sense-margin summarize self-test in check:ci
- **PR #206**: ci: bind the decision-0005 PVT grid to the spec, run the pdk_env self-test in CI
- **PR #202**: docs(sim): record why the controller SDF cannot be produced at the pinned klt (7.digital stays uncited)
- **Issue #201** (closed): Wire sim/sense-margin/test_summarize.py into check:ci: 209 lines of green regression test whose docstring cites a stale 'not run' precedent
- **Issue #196** (closed): Bind the decision-0005 PVT grid in sim/lib/pdk_env.sh to the spec in CI, as check-item6-digital.sh does for the digital extract
- **Issue #176** (closed): Assert engine_versions in the program-select summarizer self-test: an empty list is the silent failure mode of the new provenance field
- **Issue #174** (closed): T1 item 7 (digital): SDF-annotated klt functional-verification re-run on the as-built controller netlist

### 2026-11-15

- **PR #207**: feat(layout): klt lvs the routed controller against its as-built netlist
- **PR #192**: docs: point the root README CI list at signoff/README.md and complete that list
- **Issue #173** (closed): T1 item 4 (digital): klt lvs of the routed controller against its as-built netlist
- **Issue #133** (closed): Root README understates which signoff checks CI runs
- **PR #210**: ci(harness): drop redundant item 2 stream-hash step
- **PR #197**: docs: state the README position as sense path simulated across PVT
- **PR #189**: refactor(sim): single-source the fleet-checked model-file list in sim/pdk.json
- **PR #186**: docs(sim): record klt 0.8.0 provenance of the committed controller-fv reports
- **PR #168**: fix(rtl): assert no latch survives synthesis instead of scraping the Yosys log
- **PR #158**: fix: record the simulator version that ran the corners, not the local probe
- **PR #157**: fix(sim): drop the stale sense "not simulated" statements from the corner-bench summarizers
- **PR #199**: refactor(signoff): single-source the pinned-klt uvx incantation in signoff/klt.sh
- **PR #190**: refactor(sim): single-source the decision-0005 PVT corner grid in sim/lib/pdk_env.sh
- **PR #184**: fix(sim): refuse a present-but-empty program-select report before folding
- **PR #180**: test(sim): run the program-select summarize self-test in check:ci
- **PR #171**: docs: roadmap as of 2026-11-13
- **PR #194**: refactor(verification): drop the caller-less --emit-klt-requests mode
- **PR #165**: build(layout): re-establish the digital stream on the pinned klt and route the PDN through the gf180mcu_7t_6M preset
- **Issue #205** (closed): CI never runs the sim/* summarizer unit tests (discovery is scoped to scripts/ci)
- **Issue #182** (closed): Drop the redundant 'Item 2 (analog) stream matches its record' CI step: layout/attest.sh --check already covers both its failure modes
- **Issue #181** (closed): README still reads "spec ratified" at both line 13 and line 80 — the committed evidence reaches the "sense path simulated across PVT" rung
- **Issue #167** (closed): Single-source the fleet-checked model-file list: pdk_env.sh loops one copy while every record's variant_simulated names another
- **Issue #161** (closed): rtl/synth.sh reports twice the real latch count: replace the hand-rolled log scraper with a Yosys assertion
- **Issue #155** (closed): sim/controller-fv reports are klt schema_version 1; the pinned klt now emits 2
- **Issue #151** (closed): Remove the stale 'not simulated' sense statements from the corner-bench summarizers: new records still name closed #36 for effects sim/sense-mc now simulates
- **Issue #150** (closed): Remove the local ngspice -v probe from the batch benches: 4 of 14 records name ngspice 42 while every corner ran on the fleet's ngspice 46
- **Issue #191** (closed): Remove dead --emit-klt-requests mode from verification/runner.py: no caller since #148
- **Issue #188** (closed): Single-source the pinned-klt incantation: 8 scripts hand-roll it in 4 shapes and 8 of 9 give no diagnosable error when uvx is absent
- **Issue #187** (closed): Single-source the ratified decision-0005 PVT grid: four benches retype the corner set with no binding to the spec
- **Issue #177** (closed): Refuse an empty report in sim/program-select/summarize.py: after #146 a present-but-empty report still records complete: true and selects the narrowest width
- **Issue #175** (closed): Wire sim/program-select/test_summarize.py into check:ci: 141 lines of regression test that nothing runs
- **Issue #154** (closed): Establish the digital stream on the pinned klt 0.9.0, folding in the hand-written PDN block -> preset: gf180mcu_7t_6M

### 2026-11-14

- **PR #178**: fix(sim): load the sense-margin request set by name so a partial set is refused
- **PR #156**: refactor: compose probe decks from sense.cir.in and the committed netlist
- **Issue #169** (closed): Remove the report glob in sim/sense-margin/summarize.py: a partial set is recorded and the negative control can be graded over half its requests
- **Issue #144** (closed): Remove the copied bench body and subcircuits from sim/sense-margin/probe/probe.cir.in: build the 14 probe decks from sense.cir.in and the committed netlist
- **PR #153**: verification: run the controller bench only through klt functional-verification
- **PR #170**: docs(sim): anchor probe-table sizing claims to their gen_probe.sh rows
- **PR #162**: docs: attribute the split_cuts PDN workaround to klt 0.8.0, not the pinned preset
- **PR #159**: fix(sim): load the program-select grid by name so a partial set is refused
- **PR #152**: docs: drop the retyped tool-version column from the testbench inventory
- **Issue #148** (closed): Remove the second controller-bench execution path: runner.py runs cocotb directly while the committed evidence comes from klt functional-verification
- **Issue #160** (closed): probe/README.md:20 claims `both` sizing is what the schematic carries; the netlist carries the 8u/2.24u pair
- **Issue #149** (closed): Correct two false statements in layout/README.md about the gf180mcu_7t_6M PDN preset: it does combine with overrides, and the pinned klt no longer emits split_cuts
- **Issue #146** (closed): Remove the report glob in sim/program-select/summarize.py: a partial result set is recorded as complete and can select a narrower width
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
