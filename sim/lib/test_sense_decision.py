#!/usr/bin/env python3
"""Check that both sense benches share sense_decision's definitions and finite check.

Definitions gives RESOLVED_DEF and DECISION_BIT_DEF distinct sentinel strings
before importing the summarizer, then checks its emitted record. A bench
that copies either definition or swaps the two fields fails the check.
Finite exercises sense_decision.finite directly and drives both summarizers
over synthetic boolean and integer voltage readings.

Each summarizer's main() is driven over synthetic corners with bench_record
mocked out, so this is hermetic: no report set, no committed record, no
simulation. Neither bench directory is a valid module name (hyphen), so both
summarize.py files are imported by path.

    python3 -I sim/lib/test_sense_decision.py

Exit 0 = all cases pass.
"""
import contextlib
import importlib.util
import io
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bench_record  # noqa: E402  (needs the path insert above under python3 -I)
import sense_decision  # noqa: E402

VDD = 3.3


def corner(proc, temp, vdd, sbl, sref, cp, cn, so):
    ms = [{"name": n, "value": v} for n, v in
          (("v_sbl", sbl), ("v_sref", sref), ("v_cp", cp), ("v_cn", cn), ("v_sense_out", so))]
    return {"process": proc, "temperature_c": temp, "supply_v": {"vdd33": vdd}, "measurements": ms}


def good(proc="tt"):
    """One resolved corner reading the programmed bit."""
    return corner(proc, 25, VDD, 1.0, 0.9, VDD, 0.0, VDD)


def intact(proc="tt"):
    """One resolved corner reading the intact bit: margin on the correct side."""
    return corner(proc, 25, VDD, 0.9, 1.0, VDD, 0.0, 0.0)


def load_summarize(bench):
    """sim/<bench>/summarize.py imported by path: the dir name is not a module name."""
    path = os.path.abspath(os.path.join(HERE, "..", bench, "summarize.py"))
    spec = importlib.util.spec_from_file_location("summarize_%s" % bench.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_main(mod, argv, reports):
    """Drive one summarizer's main() with bench_record mocked; return its record.

    The record is written before any incomplete-set SystemExit, so both benches
    are covered by the same catch.
    """
    out = {}
    with mock.patch.object(sys, "argv", argv), \
            mock.patch.object(bench_record, "add_common_args", lambda ap: None), \
            mock.patch.object(bench_record, "load_reports", lambda d, stems: reports), \
            mock.patch.object(bench_record, "pvt_axes", lambda r: (["tt"], [25], [{"vdd33": VDD}])), \
            mock.patch.object(bench_record, "collect_env", lambda rep, *a: rep), \
            mock.patch.object(bench_record, "header", lambda *a: {}), \
            mock.patch.object(bench_record, "write_record", lambda d, rec: out.update(rec)), \
            contextlib.redirect_stdout(io.StringIO()):
        try:
            mod.main()
        except SystemExit:
            pass
    return out


@mock.patch.multiple(sense_decision, RESOLVED_DEF="sentinel resolved",
                     DECISION_BIT_DEF="sentinel decision bit")
class Definitions(unittest.TestCase):
    def test_sense_margin_emits_the_shared_definitions(self):
        mod = load_summarize("sense-margin")
        argv = ["summarize.py", "rec", "--rref", "400", "--rref-control", "500",
                "--rfuse-intact", "200", "--rfuse-programmed", "900",
                "--rfuse-control", "600", "--t-pre", "1n", "--t-out", "2n",
                "--t-edge", "1n"]
        reports = {"bench_rf200_rr400": {"corners": [intact()]},
                   "bench_rf900_rr400": {"corners": [good()]},
                   "control_rf600_rr500": {"corners": [good()]}}
        d = run_main(mod, argv, reports)["definitions"]
        self.assertEqual(d["resolved"], sense_decision.RESOLVED_DEF)
        self.assertEqual(d["decision_bit"], sense_decision.DECISION_BIT_DEF)

    def test_sense_breakeven_emits_the_shared_definitions(self):
        mod = load_summarize("sense-breakeven")
        argv = ["summarize.py", "rec", "--rref", "400", "--rfuse", "300 400",
                "--t-pre", "1n", "--t-out", "2n", "--t-edge", "1n"]
        reports = {}
        for o in ("300", "400"):
            for stem in ("ideal_rf%s_rr400" % o, "phys_rf%s_rrphys" % o):
                reports[stem] = {"corners": [good()]}
        d = run_main(mod, argv, reports)["definitions"]
        self.assertEqual(d["resolved"], sense_decision.RESOLVED_DEF)
        self.assertEqual(d["decision_bit"], sense_decision.DECISION_BIT_DEF)


class Finite(unittest.TestCase):
    MARGIN_ARGV = ["summarize.py", "rec", "--rref", "400", "--rref-control", "500",
                   "--rfuse-intact", "200", "--rfuse-programmed", "900",
                   "--rfuse-control", "200", "--t-pre", "1n", "--t-out", "2n",
                   "--t-edge", "1n"]
    BREAKEVEN_ARGV = ["summarize.py", "rec", "--rref", "400", "--rfuse", "260 630",
                      "--t-pre", "1n", "--t-out", "2n", "--t-edge", "1n"]

    def test_predicate_accepts_numbers_and_rejects_booleans(self):
        for v in (0, 1, -2, 0.0, 3.3, -0.5):
            with self.subTest(v=v):
                self.assertTrue(sense_decision.finite(v))
        for v in (True, False, None, float("nan"), float("inf"), float("-inf"), "0.5"):
            with self.subTest(v=v):
                self.assertFalse(sense_decision.finite(v))

    def test_both_summarizers_use_shared_predicate_without_math_import(self):
        for bench in ("sense-margin", "sense-breakeven"):
            with self.subTest(bench=bench):
                mod = load_summarize(bench)
                self.assertIs(mod.finite, sense_decision.finite)
                self.assertNotIn("math", vars(mod))

    def test_sense_margin_rejects_boolean_sense_line_voltage(self):
        mod = load_summarize("sense-margin")
        argv = ["summarize.py", "rec", "--rref", "400", "--rref-control", "500",
                "--rfuse-intact", "140 200", "--rfuse-programmed", "900",
                "--rfuse-control", "200", "--t-pre", "1n", "--t-out", "2n",
                "--t-edge", "1n"]
        reports = {
            "bench_rf140_rr400": {"corners": [corner("tt", 25, VDD, False, 0.5, VDD, 0, 0.0)]},
            "bench_rf200_rr400": {"corners": [intact()]},
            "bench_rf900_rr400": {"corners": [corner("tt", 25, VDD, True, 0.5, VDD, 0, VDD)]},
            "control_rf200_rr500": {"corners": [corner("tt", 25, VDD, True, 0.5, VDD, 0, VDD)]},
        }
        rec = run_main(mod, argv, reports)
        for rf in ("140", "900"):
            with self.subTest(rf=rf):
                fuse = rec["fuses"][rf]
                pt = fuse["point_list"][0]
                self.assertIsNone(pt["margin_v"])
                self.assertIsNone(pt["signed_margin_v"])
                self.assertFalse(pt["resolved"])
                self.assertIsNone(pt["decision_bit"])
                self.assertFalse(pt["decision_ok"])
                self.assertFalse(fuse["complete"])
                self.assertIsNone(fuse["min_signed_margin_v"])
                self.assertFalse(fuse["all_margin_positive"])
        self.assertFalse(rec["complete"])
        self.assertFalse(rec["analog_margin_positive_everywhere"])
        self.assertFalse(rec["negative_control"]["demonstrates_bench_can_fail"])

    def test_sense_breakeven_rejects_boolean_sense_line_voltages(self):
        mod = load_summarize("sense-breakeven")
        c260 = corner("tt", 25, VDD, False, 0.5, VDD, 0, VDD)
        c630 = corner("tt", 25, VDD, True, 0.5, VDD, 0, VDD)
        reports = {
            "ideal_rf260_rr400": {"corners": [c260]},
            "ideal_rf630_rr400": {"corners": [c630]},
            "phys_rf260_rrphys": {"corners": [c260]},
            "phys_rf630_rrphys": {"corners": [c630]},
        }
        rec = run_main(mod, self.BREAKEVEN_ARGV, reports)
        self.assertFalse(rec["complete"])
        row = rec["ideal_reference"]["corners"][0]
        self.assertEqual(row["margin_v_by_rfuse_ohm"], {"260": None, "630": None})
        self.assertIsNone(row["break_even_ohm"])
        self.assertEqual(row["break_even_basis"], "missing value")
        self.assertEqual(rec["ideal_reference"]["summary"]["with_break_even"], 0)
        # Comparator measurements are finite numbers, so break-even's own digital
        # corner grading stays intact even when v_sbl is unusable.
        self.assertTrue(row["decision_by_rfuse_ohm"]["260"]["decision_ok"])
        self.assertTrue(row["decision_by_rfuse_ohm"]["630"]["decision_ok"])
        self.assertEqual(mod.crossing([(260.0, False), (630.0, True)]), (None, "missing value"))

    def test_ordinary_integers_including_zero_still_work(self):
        margin_mod = load_summarize("sense-margin")
        margin_reports = {
            "bench_rf200_rr400": {"corners": [corner("tt", 25, VDD, 0, 0.5, VDD, 0, 0)]},
            "bench_rf900_rr400": {"corners": [corner("tt", 25, VDD, 1, 0.5, VDD, 0, VDD)]},
            "control_rf200_rr500": {"corners": [corner("tt", 25, VDD, 1, 0, VDD, 0, VDD)]},
        }
        mrec = run_main(margin_mod, self.MARGIN_ARGV, margin_reports)
        self.assertTrue(mrec["complete"])
        self.assertTrue(mrec["analog_margin_positive_everywhere"])
        self.assertTrue(mrec["decision_correct_everywhere"])
        self.assertTrue(mrec["negative_control"]["demonstrates_bench_can_fail"])
        self.assertEqual(mrec["fuses"]["200"]["min_signed_margin_v"], 0.5)
        self.assertEqual(mrec["fuses"]["900"]["min_signed_margin_v"], 0.5)

        be_mod = load_summarize("sense-breakeven")
        c260 = corner("tt", 25, VDD, 0, 0.5, VDD, 0, VDD)
        c630 = corner("tt", 25, VDD, 1, 0.5, VDD, 0, VDD)
        be_reports = {
            "ideal_rf260_rr400": {"corners": [c260]},
            "ideal_rf630_rr400": {"corners": [c630]},
            "phys_rf260_rrphys": {"corners": [c260]},
            "phys_rf630_rrphys": {"corners": [c630]},
        }
        brec = run_main(be_mod, self.BREAKEVEN_ARGV, be_reports)
        self.assertTrue(brec["complete"])
        row = brec["ideal_reference"]["corners"][0]
        self.assertEqual(row["margin_v_by_rfuse_ohm"], {"260": -0.5, "630": 0.5})
        self.assertAlmostEqual(row["break_even_ohm"], 445.0)
        self.assertEqual(brec["ideal_reference"]["summary"]["digital"]["lowest_all_corner_rfuse_ohm"], 260.0)

    def test_missing_values_keep_each_benchs_grading_criteria(self):
        margin_mod = load_summarize("sense-margin")
        margin_reports = {
            "bench_rf200_rr400": {"corners": [intact()]},
            "bench_rf900_rr400": {"corners": [corner("tt", 25, VDD, 1.0, 0.5, None, 0, VDD)]},
            "control_rf200_rr500": {"corners": [corner("tt", 25, VDD, 1.0, 0.5, VDD, 0, VDD)]},
        }
        mrec = run_main(margin_mod, self.MARGIN_ARGV, margin_reports)
        pt = mrec["fuses"]["900"]["point_list"][0]
        self.assertIsNone(pt["margin_v"])
        self.assertFalse(pt["decision_ok"])
        self.assertFalse(mrec["complete"])

        be_mod = load_summarize("sense-breakeven")
        c260 = corner("tt", 25, VDD, 0.0, 0.5, None, 0, VDD)
        c630 = corner("tt", 25, VDD, 1.0, 0.5, VDD, 0, VDD)
        be_reports = {
            "ideal_rf260_rr400": {"corners": [c260]},
            "ideal_rf630_rr400": {"corners": [c630]},
            "phys_rf260_rrphys": {"corners": [c260]},
            "phys_rf630_rrphys": {"corners": [c630]},
        }
        brec = run_main(be_mod, self.BREAKEVEN_ARGV, be_reports)
        self.assertTrue(brec["complete"])
        row = brec["ideal_reference"]["corners"][0]
        self.assertAlmostEqual(row["break_even_ohm"], 445.0)
        self.assertFalse(row["decision_by_rfuse_ohm"]["260"]["decision_ok"])
        self.assertEqual(brec["ideal_reference"]["summary"]["digital"]["lowest_all_corner_rfuse_ohm"], 630.0)


if __name__ == "__main__":
    unittest.main()
