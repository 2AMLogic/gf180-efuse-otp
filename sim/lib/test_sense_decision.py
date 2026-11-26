#!/usr/bin/env python3
"""Cross-bench pin for the two decision record strings: what sim/sense-margin
and sim/sense-breakeven emit as definitions["resolved"] and
definitions["decision_bit"] must be the RESOLVED_DEF / DECISION_BIT_DEF
constants from sim/lib/sense_decision.py, so the two benches cannot describe
decide() differently. A reword in one summarizer -- or a literal reintroduced
in place of the constants -- fails here even though each bench's own
self-test may still pass.

Each summarizer's main() is driven over one synthetic corner with bench_record
mocked out, so this is hermetic: no report set, no committed record, no
simulation. Neither bench directory is a valid module name (hyphen), so both
summarize.py files are imported by path.

    python3 -I sim/lib/test_sense_decision.py

Exit 0 = all cases pass.
"""
import importlib.util
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bench_record  # noqa: E402  (needs the path insert above under python3 -I)
from sense_decision import DECISION_BIT_DEF, RESOLVED_DEF  # noqa: E402

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
            mock.patch.object(bench_record, "write_record", lambda d, rec: out.update(rec)):
        try:
            mod.main()
        except SystemExit:
            pass
    return out


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
        self.assertEqual(d["resolved"], RESOLVED_DEF)
        self.assertEqual(d["decision_bit"], DECISION_BIT_DEF)

    def test_sense_breakeven_emits_the_shared_definitions(self):
        mod = load_summarize("sense-breakeven")
        argv = ["summarize.py", "rec", "--rref", "400", "--rfuse", "300 400",
                "--t-pre", "1n", "--t-out", "2n", "--t-edge", "1n"]
        reports = {}
        for o in ("300", "400"):
            for stem in ("ideal_rf%s_rr400" % o, "phys_rf%s_rrphys" % o):
                reports[stem] = {"corners": [good()]}
        d = run_main(mod, argv, reports)["definitions"]
        self.assertEqual(d["resolved"], RESOLVED_DEF)
        self.assertEqual(d["decision_bit"], DECISION_BIT_DEF)


if __name__ == "__main__":
    unittest.main()
