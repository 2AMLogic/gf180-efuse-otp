#!/usr/bin/env python3
"""Self-test for summarize.py: the record describes the submitted grid, not
whatever reports happen to be present, and not whatever those reports happen
to contain.

Fixture is the newest committed record under records/ (read-only; reports are
copied into a temp directory and the committed record is never touched). The
grid and the provenance arguments are read back out of that record, so this
test does not restate them.

    python3 -I sim/program-select/test_summarize.py

Exit 0 = all cases pass. Run by the local hermetic gate `npm run -s check:ci`,
alongside sim/lib/test_pdk_env.sh. Not run by the GitHub workflow, whose only
unittest discovery step is scoped to scripts/ci.
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


def empty_corners(rep):
    """A report that came back present but measured nothing.

    `corner_count` is left as klt declared it, so the report contradicts
    itself -- the shape the summarizer's cross-check is aimed at.
    """
    rep["corners"] = []


def empty_corners_and_count(rep):
    """The same, self-consistently: no corners and none declared."""
    rep["corners"] = []
    rep["corner_count"] = 0


def newest_record():
    """The newest records/<stamp>-<rev> directory holding a record.json."""
    stamps = sorted(d for d in os.listdir(RECORDS)
                    if os.path.isfile(os.path.join(RECORDS, d, "record.json")))
    if not stamps:
        raise unittest.SkipTest("no committed record under %s" % RECORDS)
    return os.path.join(RECORDS, stamps[-1])


class Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = newest_record()
        cls.committed = load_json(os.path.join(cls.src, "record.json"))
        cls.fuse_ohms = [int(r) for r in cls.committed["pvt"]["fuse_ohm"]]
        cls.widths_um = [int(w["w_um"]) for w in cls.committed["widths"]]
        cls.stems = ["cell_r%d_w%d" % (r, w)
                     for r in cls.fuse_ohms for w in cls.widths_um]
        cls.args = [
            "--ireq", repr(cls.committed["requirement"]["i_fuse_min_a"]),
            "--vmax", repr(cls.committed["assumptions"]["voltage_limit_v"]["value"]),
            "--rroute", repr(cls.committed["assumptions"]["routing_resistance_ohm"]["value"]),
            "--fuse-ohms", " ".join(str(r) for r in cls.fuse_ohms),
            "--widths-um", " ".join(str(w) for w in cls.widths_um),
            "--pdk-rev", cls.committed["pdk_revision"],
            "--stamp", cls.committed["timestamp_utc"],
            "--klt", cls.committed["klt_version"],
        ]

    def run_case(self, drop=(), edit=None, edits=(), args=None):
        """Copy the fixture's reports (minus `drop`), optionally edit some, summarize.

        `edit` is a single (stem, mutate) pair; `edits` an iterable of them.
        Returns (completed process, record dict or None).
        """
        rec = tempfile.mkdtemp(prefix="program-select-test-")
        self.addCleanup(shutil.rmtree, rec, True)
        for stem in self.stems:
            if stem in drop:
                continue
            dst = os.path.join(rec, "sets", stem)
            os.makedirs(dst)
            shutil.copyfile(os.path.join(self.src, "sets", stem, "report.json"),
                            os.path.join(dst, "report.json"))
        for stem, mutate in (list(edits) + ([edit] if edit is not None else [])):
            path = os.path.join(rec, "sets", stem, "report.json")
            rep = load_json(path)
            mutate(rep)
            with open(path, "w") as f:
                json.dump(rep, f)
        p = subprocess.run([sys.executable, "-I", SUMMARIZE, rec]
                           + (self.args if args is None else args),
                           capture_output=True, text=True)
        out = os.path.join(rec, "record.json")
        return p, (load_json(out) if os.path.isfile(out) else None)

    def test_a_complete_set_describes_the_whole_grid(self):
        p, rec = self.run_case()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIsNotNone(rec)
        self.assertTrue(rec["complete"])
        self.assertEqual([w["w_um"] for w in rec["widths"]],
                         [float(w) for w in sorted(self.widths_um)])
        corners = len(load_json(os.path.join(
            self.src, "sets", self.stems[0], "report.json"))["corners"])
        for w in rec["widths"]:
            self.assertEqual(w["points"], corners * len(self.fuse_ohms))
        # The verdict the committed record reached over the same reports.
        self.assertEqual(rec["chosen_w_um"], self.committed["chosen_w_um"])
        self.assertEqual(rec["pvt"]["fuse_ohm"], self.fuse_ohms)

    def test_b_one_fuse_value_missing_is_refused(self):
        drop = [s for s in self.stems
                if s.startswith("cell_r%d_w" % max(self.fuse_ohms))]
        p, rec = self.run_case(drop=drop)
        self.assertEqual(p.returncode, 4, p.stdout + p.stderr)
        self.assertIsNone(rec, "a partial set must not be recorded")
        for stem in drop:
            self.assertIn(stem, p.stderr)

    def test_c_no_reports_at_all_is_refused(self):
        p, rec = self.run_case(drop=self.stems)
        self.assertEqual(p.returncode, 4, p.stdout + p.stderr)
        self.assertIsNone(rec, "an empty set must not be recorded")

    def test_d_present_report_without_a_current_is_incomplete(self):
        def blank_first_current(rep):
            for m in rep["corners"][0]["measurements"]:
                if m["name"] == "i_fuse":
                    m["value"] = None
        p, rec = self.run_case(edit=(self.stems[0], blank_first_current))
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertIsNotNone(rec, "an incomplete set is still recorded for diagnosis")
        self.assertFalse(rec["complete"])
        self.assertIn("sets/cell_r<ohm>_w<um>/report.json", p.stdout)

    def test_e_an_empty_grid_is_rejected(self):
        for flag in ("--fuse-ohms", "--widths-um"):
            with self.subTest(flag=flag):
                args = list(self.args)
                args[args.index(flag) + 1] = ""
                p, rec = self.run_case(args=args)
                self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                self.assertIsNone(rec, "an empty grid must not be recorded")

    def test_f_every_report_present_but_empty_is_refused(self):
        """All 15 reports present with no corners: nothing was measured.

        Two shapes. `declared` leaves klt's own `corner_count` in place, so the
        report contradicts itself; `zeroed` is self-consistent, so only the
        non-empty test catches it. Before this guard both wrote a record with
        `complete: true` and exited 0 (#177 case A).
        """
        for shape, mutate in (("declared", empty_corners),
                              ("zeroed", empty_corners_and_count)):
            with self.subTest(shape=shape):
                p, rec = self.run_case(edits=[(s, mutate) for s in self.stems])
                self.assertEqual(p.returncode, 4, p.stdout + p.stderr)
                self.assertIsNone(rec, "an empty set must not be recorded")
                self.assertIn("a partial set is not evidence", p.stderr)
                for stem in self.stems:
                    self.assertIn(stem, p.stderr)

    def test_g_one_full_width_with_the_rest_empty_is_refused(self):
        """The reachable case: the narrowest width folds, the others vanish.

        Before this guard this exact fixture exited 0 and wrote a record with
        `complete: true` describing one of its five widths, the other four
        absent with no diagnostic -- and with a requirement near the narrow
        widths' boundary the same shape moves `chosen_w_um` (#177 case B; the
        PR records a 40 um -> 20 um flip from emptying one report). The widths
        that returned nothing must be named, and no record may be written.
        """
        keep = min(self.widths_um)
        kept = ["cell_r%d_w%d" % (r, keep) for r in self.fuse_ohms]
        emptied = [s for s in self.stems if s not in kept]
        p, rec = self.run_case(edits=[(s, empty_corners) for s in emptied])
        self.assertEqual(p.returncode, 4, p.stdout + p.stderr)
        self.assertIsNone(rec, "a set missing four of five widths must not be recorded")
        for stem in emptied:
            self.assertIn(stem, p.stderr)
        for stem in kept:
            self.assertNotIn(stem, p.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
