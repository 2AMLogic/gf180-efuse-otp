#!/usr/bin/env python3
"""Self-test for the break-even interpolation and the folded digital decision:
python3 -I sim/sense-breakeven/test_summarize.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import summarize  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from sense_decision import decide  # noqa: E402

VDD = 3.3


def corner(proc, temp, vdd, sbl, sref, cp, cn, so):
    ms = [{"name": n, "value": v} for n, v in
          (("v_sbl", sbl), ("v_sref", sref), ("v_cp", cp), ("v_cn", cn), ("v_sense_out", so))]
    return {"process": proc, "temperature_c": temp, "supply_v": {"vdd33": vdd}, "measurements": ms}


def good(proc="tt"):   # resolved, programmed bit
    return corner(proc, 25, VDD, 1.0, 0.9, VDD, 0.0, VDD)


class Decide(unittest.TestCase):
    def test_resolve_threshold_inclusive(self):
        self.assertTrue(decide(0.5 * VDD, 0.0, VDD, VDD, 1)[0])
        self.assertFalse(decide(0.5 * VDD - 1e-9, 0.0, VDD, VDD, 1)[0])

    def test_logic_thresholds_inclusive(self):
        self.assertEqual(decide(VDD, 0, 0.7 * VDD, VDD, 1)[1], 1)
        self.assertEqual(decide(VDD, 0, 0.3 * VDD, VDD, 0)[1], 0)
        self.assertIsNone(decide(VDD, 0, 0.5 * VDD, VDD, 1)[1])

    def test_unresolved_latch_with_high_output_not_ok(self):
        res, bit, ok = decide(1.0, 0.9, VDD, VDD, 1)
        self.assertEqual((res, bit, ok), (False, 1, False))

    def test_missing_or_nonfinite(self):
        self.assertEqual(decide(None, 0, VDD, VDD, 1), (False, None, False))
        self.assertEqual(decide(VDD, 0, float("nan"), VDD, 1), (False, None, False))


class Digital(unittest.TestCase):
    def fold(self, by_ohm):
        reports = {"s%g" % o: {"corners": cs} for o, cs in by_ohm.items()}
        return summarize.fold(reports, {o: "s%g" % o for o in by_ohm})

    def test_counts_and_lowest_all_corner(self):
        wrong = corner("ff", 25, VDD, 0.9, 1.0, VDD, 0.0, 0.0)  # valid wrong bit
        rows = self.fold({300: [wrong, good("tt")], 400: [good("ff"), good("tt")]})
        d = summarize.digital(rows, [300, 400])
        self.assertEqual(d["correct_corners_by_rfuse_ohm"], {"300": 1, "400": 2})
        self.assertEqual(d["lowest_all_corner_rfuse_ohm"], 400)
        # the wrong-bit reading leaves the analog crossing usable
        ff = [r for r in rows if r["process"] == "ff"][0]
        self.assertEqual(ff["decision_by_rfuse_ohm"]["300"]["decision_bit"], 0)
        self.assertAlmostEqual(ff["break_even_ohm"], 350.0)

    def test_equality_at_thresholds_counts(self):
        edge = corner("tt", 25, VDD, 1.0, 0.9, 0.5 * VDD, 0.0, 0.7 * VDD)
        d = summarize.digital(self.fold({300: [edge], 400: [edge]}), [300, 400])
        self.assertEqual(d["lowest_all_corner_rfuse_ohm"], 300)

    def test_intermediate_output_and_unresolved_do_not_count(self):
        mid = corner("tt", 25, VDD, 1.0, 0.9, VDD, 0.0, 0.5 * VDD)
        unres = corner("tt", 25, VDD, 1.0, 0.9, 1.0, 0.9, VDD)
        d = summarize.digital(self.fold({300: [mid], 400: [unres]}), [300, 400])
        self.assertEqual(d["correct_corners_by_rfuse_ohm"], {"300": 0, "400": 0})
        self.assertIsNone(d["lowest_all_corner_rfuse_ohm"])

    def test_missing_corner_cannot_qualify(self):
        # 400 ohm lacks the ff corner entirely; 500 has both
        rows = self.fold({400: [good("tt")], 500: [good("tt"), good("ff")]})
        d = summarize.digital(rows, [400, 500])
        self.assertEqual(d["correct_corners_by_rfuse_ohm"], {"400": 1, "500": 2})
        self.assertEqual(d["lowest_all_corner_rfuse_ohm"], 500)

    def test_unusable_measurement_cannot_qualify(self):
        bad = corner("tt", 25, VDD, 1.0, 0.9, None, 0.0, VDD)
        d = summarize.digital(self.fold({300: [bad], 400: [bad]}), [300, 400])
        self.assertIsNone(d["lowest_all_corner_rfuse_ohm"])

    def test_no_rows(self):
        self.assertIsNone(summarize.digital([], [300])["lowest_all_corner_rfuse_ohm"])


class Crossing(unittest.TestCase):
    def test_interpolates(self):
        be, _ = summarize.crossing([(300, -0.02), (340, -0.01), (380, 0.01), (420, 0.03)])
        self.assertAlmostEqual(be, 360.0)

    def test_no_sign_change_is_not_extrapolated(self):
        self.assertIsNone(summarize.crossing([(300, 0.01), (340, 0.02)])[0])

    def test_two_sign_changes_refused(self):
        self.assertIsNone(summarize.crossing([(300, -1), (340, 1), (380, -1)])[0])

    def test_missing_value(self):
        self.assertIsNone(summarize.crossing([(300, None), (340, 1)])[0])


class Definitions(unittest.TestCase):
    """main() emits one top-level definitions block and changes nothing else."""
    KEYS = {"resolved", "decision_bit", "decision_ok",
            "correct_corners_by_rfuse_ohm", "lowest_all_corner_rfuse_ohm"}

    def run_main(self):
        from unittest import mock
        import bench_record
        ohms = ["300", "400"]
        reports = {}
        for o in ohms:
            for stem in ("ideal_rf%s_rr400" % o, "phys_rf%s_rrphys" % o):
                reports[stem] = {"corners": [good("tt")]}
        out = {}
        argv = ["summarize.py", "rec", "--rref", "400", "--rfuse", " ".join(ohms),
                "--t-pre", "1n", "--t-out", "2n", "--t-edge", "1n"]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(bench_record, "add_common_args", lambda ap: None), \
                mock.patch.object(bench_record, "load_reports", lambda d, stems: reports), \
                mock.patch.object(bench_record, "pvt_axes", lambda r: (["tt"], [25], [{"vdd33": VDD}])), \
                mock.patch.object(bench_record, "collect_env", lambda *a: None), \
                mock.patch.object(bench_record, "header", lambda *a: {}), \
                mock.patch.object(bench_record, "write_record", lambda d, rec: out.update(rec)):
            try:
                summarize.main()
            except SystemExit:
                pass
        return out

    def test_definitions_present_and_inert(self):
        rec = self.run_main()
        d = rec["definitions"]
        self.assertEqual(set(d), self.KEYS)
        self.assertEqual(d["resolved"], "|v(cp) - v(cn)| >= 0.5 * vdd33 after the edge")
        self.assertEqual(d["decision_bit"], "1 if v(sense_out) >= 0.7 vdd33, 0 if <= 0.3 vdd33, else null")
        self.assertIn("programmed bit (1)", d["decision_ok"])
        self.assertIn("below the reference", d["decision_ok"])
        self.assertIn("swept", d["lowest_all_corner_rfuse_ohm"])
        self.assertIn("null", d["lowest_all_corner_rfuse_ohm"])
        self.assertNotIn("definitions", rec["ideal_reference"])
        self.assertNotIn("definitions", rec["physical_reference"])
        self.assertEqual(rec["ideal_reference"]["summary"]["digital"]["lowest_all_corner_rfuse_ohm"], 300)


if __name__ == "__main__":
    unittest.main()
