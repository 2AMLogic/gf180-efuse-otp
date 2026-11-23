#!/usr/bin/env python3
"""Self-test for bench_record.load_reports() and bench_record.pvt_axes(): a
partial report set is refused with exit 4 before anything is returned, a
complete set comes back as {stem: report}, and the PVT axes those reports
share are derived (order kept, temps sorted) or the disagreement is refused.

Fixtures are hand-built reports in a temp directory; no committed record is
read, so this test is hermetic and needs no bench data.

    python3 -I sim/lib/test_bench_record.py

Exit 0 = all cases pass. Run by the local hermetic gate `npm run -s check:ci`.
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench_record  # noqa: E402  (needs the path insert above under python3 -I)


def report(corners=2):
    """A well-formed klt report: `corner_count` agrees with `corners`."""
    return {"corner_count": corners,
            "corners": [{"name": "c%d" % k} for k in range(corners)]}


def grid(corners):
    """A report whose corners carry the PVT fields pvt_axes() reads."""
    return {"corner_count": len(corners), "corners": corners}


def corner(process, temp, supply_v):
    return {"process": process, "temperature_c": temp, "supply_v": supply_v}


class Test(unittest.TestCase):
    def setUp(self):
        self.rec = tempfile.mkdtemp(prefix="bench-record-test-")
        self.addCleanup(shutil.rmtree, self.rec, True)

    def put(self, stem, rep):
        d = os.path.join(self.rec, "sets", stem)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "report.json"), "w") as f:
            json.dump(rep, f)

    def refuse(self, stems):
        """Run load_reports expecting the single exit-4 refusal; return stderr."""
        err = io.StringIO()
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(err):
            bench_record.load_reports(self.rec, stems)
        self.assertEqual(cm.exception.code, 4)
        out = err.getvalue()
        self.assertEqual(out.count("a partial set is not evidence"), 1,
                         "one refusal, one trailer")
        self.assertIn("/set-report.json, ", out)
        self.assertIn("/klt.err)", out)
        return out

    def test_absent_report_is_refused(self):
        self.put("a", report())
        out = self.refuse(["a", "b"])
        self.assertIn("no report for 1 of 2 expected requests: b", out)
        self.assertNotIn("no usable corners", out)

    def test_hollow_report_is_refused(self):
        self.put("a", report())
        self.put("b", {"corner_count": 2, "corners": []})
        out = self.refuse(["a", "b"])
        self.assertIn("no usable corners in 1 of 2 expected reports: "
                      "b (corner_count=2, corners=0)", out)
        self.assertNotIn("no report for", out)

    def test_truncated_report_is_refused(self):
        """Fewer corners than corner_count declared is a short set."""
        self.put("a", {"corner_count": 3, "corners": report(1)["corners"]})
        out = self.refuse(["a"])
        self.assertIn("no usable corners in 1 of 1 expected reports: "
                      "a (corner_count=3, corners=1)", out)

    def test_report_without_corner_count_is_refused(self):
        """No declared count: the cross-check cannot pass, so the report is hollow."""
        self.put("a", {"corners": report(1)["corners"]})
        out = self.refuse(["a"])
        self.assertIn("a (corner_count=None, corners=1)", out)

    def test_mixed_absent_and_hollow_prints_both_blocks_then_one_trailer(self):
        self.put("a", report())
        self.put("c", {"corner_count": 1, "corners": []})
        out = self.refuse(["a", "b", "c"])
        self.assertIn("no report for 1 of 3 expected requests: b", out)
        self.assertIn("no usable corners in 1 of 3 expected reports: "
                      "c (corner_count=1, corners=0)", out)
        self.assertLess(out.index("no report for"), out.index("no usable corners"),
                        "absent block first, then hollow, then the trailer")
        self.assertLess(out.index("no usable corners"),
                        out.index("a partial set is not evidence"))

    def test_complete_set_is_returned(self):
        self.put("a", report(2))
        self.put("b", report(1))
        reps = bench_record.load_reports(self.rec, ["a", "b"])
        self.assertEqual(sorted(reps), ["a", "b"])
        self.assertEqual(reps["a"]["corner_count"], 2)
        self.assertEqual(len(reps["b"]["corners"]), 1)

    def test_empty_stem_list_returns_empty_dict(self):
        """A refusal is about a partial set; nothing expected is nothing partial.

        The benches each refuse an empty request list at argparse (exit 2)
        before calling this, so an empty list here is only the vacuous case.
        """
        self.assertEqual(bench_record.load_reports(self.rec, []), {})


class TestPvtAxes(unittest.TestCase):
    """pvt_axes(): the grid the reports ran, or a refusal when they differ."""

    def single(self):
        """A one-axis grid in the program-select / sense-margin shape.

        Corners are listed out of axis order (temps unsorted, a process
        repeated) so the tests show pvt_axes() ordering, not echo order.
        """
        return grid([corner("typical", 125, {"vdd": 5.5}),
                     corner("ff", 25, {"vdd": 4.5}),
                     corner("typical", -40, {"vdd": 5.0}),
                     corner("ff", 25, {"vdd": 4.5})])

    def test_consistent_multi_report_set_returns_the_shared_axes(self):
        reports = {"a": self.single(), "b": self.single()}
        self.assertEqual(bench_record.pvt_axes(reports),
                         (["typical", "ff"], [-40, 25, 125],
                          [{"vdd": 5.5}, {"vdd": 4.5}, {"vdd": 5.0}]))

    def test_process_order_is_first_seen_not_sorted(self):
        """typical/ff/ss/fs/sf is not alphabetical; the record keeps klt's order."""
        reports = {"a": grid([corner("fs", 25, {"vdd33": 3.3}),
                              corner("typical", 25, {"vdd33": 3.3}),
                              corner("ff", 25, {"vdd33": 3.3})])}
        process, _, _ = bench_record.pvt_axes(reports)
        self.assertEqual(process, ["fs", "typical", "ff"])

    def test_paired_supplies_keep_their_zipped_order(self):
        """A two-axis grid zipped by klt reads back as whole supply points."""
        reports = {"a": grid([corner("typical", -40, {"vdd33": 2.97, "vprog": 4.5}),
                              corner("typical", 25, {"vdd33": 3.3, "vprog": 5.0}),
                              corner("typical", 125, {"vdd33": 3.63, "vprog": 5.5})])}
        _, _, supplies = bench_record.pvt_axes(reports)
        self.assertEqual(supplies, [{"vdd33": 2.97, "vprog": 4.5},
                                    {"vdd33": 3.3, "vprog": 5.0},
                                    {"vdd33": 3.63, "vprog": 5.5}])

    def test_reports_that_ran_different_grids_are_refused(self):
        other = self.single()
        other["corners"][0]["temperature_c"] = 85
        with self.assertRaises(SystemExit) as cm:
            bench_record.pvt_axes({"a": self.single(), "b": other})
        self.assertNotEqual(cm.exception.code, 0)
        self.assertIn("disagree on the corner grid", str(cm.exception))
        self.assertIn("a=", str(cm.exception))
        self.assertIn("b=", str(cm.exception))

    def test_no_reports_at_all_is_refused(self):
        with self.assertRaises(SystemExit) as cm:
            bench_record.pvt_axes({})
        self.assertNotEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
