#!/usr/bin/env python3
"""Self-test for summarize.py: the record describes the submitted request set,
not whatever reports happen to be present.

Fixture is the newest committed record under records/ (read-only; reports are
copied into a temp directory and the committed record is never touched). The
request set and the provenance arguments are read back out of that record, so
this test does not restate them.

    python3 -I sim/sense-margin/test_summarize.py

Exit 0 = all cases pass. Run by the local hermetic gate `npm run -s check:ci`,
alongside sim/program-select/test_summarize.py and sim/lib/test_pdk_env.sh.
Not run by the GitHub workflow, whose only unittest discovery step is scoped
to scripts/ci.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SUMMARIZE = os.path.join(HERE, "summarize.py")
RECORDS = os.path.join(HERE, "records")


def load_json(path):
    with open(path) as f:
        return json.load(f)


def newest_record():
    """The newest records/<stamp>-<rev> directory holding a record.json."""
    stamps = sorted(d for d in os.listdir(RECORDS)
                    if os.path.isfile(os.path.join(RECORDS, d, "record.json")))
    if not stamps:
        raise unittest.SkipTest("no committed record under %s" % RECORDS)
    return os.path.join(RECORDS, stamps[-1])


# record.json also carries blocks of fixed prose: what the DUT is, the PVT grid,
# the assumptions, the definitions, the argument-derived read times and the
# verdict sentence. Those are restatements, not loaded data, and a later issue
# may legitimately reword one (#151 rewords assumptions.not_simulated) while
# sim/ records stay append-only -- so a reworded summarizer can never again
# reproduce an older record's bytes. The durable regression test is over the
# fields the loading path itself determines; the byte comparison below still
# runs whenever the prose has not drifted.
PROSE = ("dut", "pvt", "assumptions", "definitions", "measurement_times", "verdict")


def loaded(rec):
    return {k: v for k, v in rec.items() if k not in PROSE}


class Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = newest_record()
        with open(os.path.join(cls.src, "record.json"), "rb") as f:
            cls.committed_bytes = f.read()
        cls.committed = json.loads(cls.committed_bytes.decode())
        # The request set, read out of the record rather than restated: the two
        # populations are tagged per fuse value, the controls are named in the
        # negative control, and both references are recorded.
        pop = {rf: f["population"] for rf, f in cls.committed["fuses"].items()}
        cls.intact = [rf for rf, p in pop.items() if p.startswith("intact")]
        cls.programmed = [rf for rf, p in pop.items() if p.startswith("programmed")]
        cls.controls = list(cls.committed["negative_control"]["fuse_ohm"])
        cls.rref = cls.committed["assumptions"]["reference_ohm"]["value"]
        cls.rref_control = cls.committed["negative_control"]["rref_ohm"]
        cls.bench_stems = ["bench_rf%s_rr%g" % (rf, cls.rref)
                           for rf in cls.intact + cls.programmed]
        cls.control_stems = ["control_rf%s_rr%g" % (rf, cls.rref_control)
                             for rf in cls.controls]
        # A record run with --physical-reference also carries the phys_rf*_rrphys
        # requests (summarize.py's physical_reference.fuses names their fuse values).
        cls.phys_stems = (["phys_rf%s_rrphys" % rf for rf in cls.intact + cls.programmed]
                          if "physical_reference" in cls.committed else [])
        cls.stems = cls.bench_stems + cls.control_stems + cls.phys_stems
        times = cls.committed["measurement_times"]
        # "one rising edge at <t_edge>, amplitude tracks vdd33; ..." -- the only
        # place the record keeps the clock-edge argument.
        t_edge = cls.committed["assumptions"]["clock"].split(" at ", 1)[1].split(",", 1)[0]
        cls.args = [
            "--rref", repr(cls.rref),
            "--rref-control", repr(cls.rref_control),
            "--rfuse-intact", " ".join(cls.intact),
            "--rfuse-programmed", " ".join(cls.programmed),
            "--rfuse-control", " ".join(cls.controls),
            "--t-pre", times["margin_read"],
            "--t-out", times["decision_read"],
            "--t-edge", t_edge,
            "--pdk-rev", cls.committed["pdk_revision"],
            "--stamp", cls.committed["timestamp_utc"],
            "--klt", cls.committed["klt_version"],
        ]
        if cls.phys_stems:
            cls.args.append("--physical-reference")

    def run_case(self, drop=(), edit=None, args=None):
        """Copy the fixture's reports (minus `drop`), optionally edit one, summarize.

        Returns (completed process, raw record.json bytes or None).
        """
        rec = tempfile.mkdtemp(prefix="sense-margin-test-")
        self.addCleanup(shutil.rmtree, rec, True)
        for stem in self.stems:
            if stem in drop:
                continue
            dst = os.path.join(rec, "sets", stem)
            os.makedirs(dst)
            shutil.copyfile(os.path.join(self.src, "sets", stem, "report.json"),
                            os.path.join(dst, "report.json"))
        if edit is not None:
            stem, mutate = edit
            path = os.path.join(rec, "sets", stem, "report.json")
            rep = load_json(path)
            mutate(rep)
            with open(path, "w") as f:
                json.dump(rep, f)
        p = subprocess.run([sys.executable, "-I", SUMMARIZE, rec]
                           + (self.args if args is None else args),
                           capture_output=True, text=True)
        out = os.path.join(rec, "record.json")
        if not os.path.isfile(out):
            return p, None
        with open(out, "rb") as f:
            return p, f.read()

    def test_a_complete_set_reproduces_the_committed_record(self):
        """The named load must regenerate the committed record's data unchanged."""
        p, raw = self.run_case()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIsNotNone(raw)
        rec = json.loads(raw.decode())
        # The provenance header is the one deliberate difference: committed
        # records keep `ngspice_version_local` (a probe this batch-only bench
        # never ran); a regenerated record names the engines that ran the
        # corners. Since #118 a regenerated record additionally carries the
        # `tool_versions` and `corners` fields the CI record-format check
        # requires, which the committed records predate; both are asserted
        # separately below. Strip those provenance keys and the loaded data
        # must match.
        def data(r):
            return {k: v for k, v in loaded(r).items()
                    if k not in ("ngspice_version_local", "engine_versions",
                                 "tool_versions", "corners")}
        self.assertEqual(data(rec), data(self.committed),
                         "the named load must reproduce the committed record's data")
        engines = sorted({load_json(os.path.join(self.src, "sets", s, "report.json"))
                          .get("environment", {}).get("engine_version")
                          for s in self.stems} - {None})
        self.assertEqual(rec["engine_versions"], engines)
        # The #118 fields, asserted on their own so the comparison with
        # historical measurement data above stays meaningful: tool_versions
        # restates the provenance inputs, corners restates the committed
        # record's own pvt axes -- expected derived from that pvt, never a
        # retyped literal, so a fixture bump cannot strand the assertion.
        self.assertEqual(rec["tool_versions"],
                         {"klt_sim": self.committed["klt_version"],
                          "ngspice": engines})
        pvt = self.committed["pvt"]
        self.assertEqual(
            rec["corners"],
            "%d per request: %d process x %d temperature x %d vdd33 (decision 0005); see pvt"
            % (len(pvt["process"]) * len(pvt["temp_c"]) * len(pvt["vdd33_v"]),
               len(pvt["process"]), len(pvt["temp_c"]), len(pvt["vdd33_v"])))
        drifted = [k for k in PROSE if rec.get(k) != self.committed.get(k)]
        if not drifted and "engine_versions" in self.committed \
                and "tool_versions" in self.committed and "corners" in self.committed:
            self.assertEqual(raw, self.committed_bytes,
                             "no prose drift, so the re-summarize must be byte-identical")

    def test_b_a_missing_control_is_refused(self):
        """The gap this bench had: one of the two controls absent was recorded as
        complete, with demonstrates_bench_can_fail asserted over half the set."""
        for stem in self.control_stems:
            with self.subTest(stem=stem):
                p, raw = self.run_case(drop=[stem])
                self.assertEqual(p.returncode, 4, p.stdout + p.stderr)
                self.assertIsNone(raw, "a partial control set must not be recorded")
                self.assertIn(stem, p.stderr)

    def test_c_a_missing_bench_request_is_refused(self):
        drop = [self.bench_stems[-1]]
        p, raw = self.run_case(drop=drop)
        self.assertEqual(p.returncode, 4, p.stdout + p.stderr)
        self.assertIsNone(raw, "a partial set must not be recorded")
        self.assertIn(drop[0], p.stderr)

    def test_d_no_reports_at_all_is_refused(self):
        p, raw = self.run_case(drop=self.stems)
        self.assertEqual(p.returncode, 4, p.stdout + p.stderr)
        self.assertIsNone(raw, "an empty set must not be recorded")

    def test_e_a_present_but_corner_less_report_is_refused(self):
        """Present is not populated: a report that graded nothing is not evidence."""
        def empty_corners(rep):
            rep["corners"] = []
            rep["corner_count"] = 0
        for stem in (self.bench_stems[0], self.control_stems[0]):
            with self.subTest(stem=stem):
                p, raw = self.run_case(edit=(stem, empty_corners))
                self.assertEqual(p.returncode, 4, p.stdout + p.stderr)
                self.assertIsNone(raw, "a report with no corners must not be recorded")
                self.assertIn(stem, p.stderr)

    def test_f_a_truncated_report_is_refused(self):
        """corner_count is what the request asked for; fewer corners is a short set."""
        def drop_corners(rep):
            rep["corners"] = rep["corners"][:1]
        p, raw = self.run_case(edit=(self.bench_stems[0], drop_corners))
        self.assertEqual(p.returncode, 4, p.stdout + p.stderr)
        self.assertIsNone(raw, "a truncated report must not be recorded")
        self.assertIn(self.bench_stems[0], p.stderr)

    def test_g_present_report_without_values_is_incomplete(self):
        """All reports present but a point has no values: recorded for diagnosis."""
        def blank_first_margin(rep):
            for m in rep["corners"][0]["measurements"]:
                if m["name"] == "v_sbl":
                    m["value"] = None
        p, raw = self.run_case(edit=(self.bench_stems[0], blank_first_margin))
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertIsNotNone(raw, "an incomplete set is still recorded for diagnosis")
        rec = json.loads(raw.decode())
        self.assertFalse(rec["complete"])
        self.assertFalse(rec["analog_margin_positive_everywhere"])
        self.assertIn("sets/<request>/report.json", p.stdout)

    def test_h_an_empty_request_list_is_rejected(self):
        for flag in ("--rfuse-intact", "--rfuse-programmed", "--rfuse-control"):
            with self.subTest(flag=flag):
                args = list(self.args)
                args[args.index(flag) + 1] = ""
                p, raw = self.run_case(args=args)
                self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                self.assertIsNone(raw, "an empty request list must not be recorded")

    def test_i_a_missing_phys_request_is_refused(self):
        """A physical-reference record is refused when a phys_* report is absent:
        the physical reference is part of the nominal evidence, not an extra."""
        if not self.phys_stems:
            self.skipTest("newest committed record predates --physical-reference")
        for stem in self.phys_stems:
            with self.subTest(stem=stem):
                p, raw = self.run_case(drop=[stem])
                self.assertEqual(p.returncode, 4, p.stdout + p.stderr)
                self.assertIsNone(raw, "a partial physical-reference set must not be recorded")
                self.assertIn(stem, p.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
