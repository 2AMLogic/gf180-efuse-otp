"""Exercise the density limits and controller publication. Run with klt_python -I."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import klayout.db as kdb


LAYOUT = Path(__file__).resolve().parent


def write_stream(path, comp=25000, poly=14000, metal=30000):
    """Widths in nm on a 100 µm square die. A fuse marker excludes all fill."""
    layout = kdb.Layout()
    layout.dbu = 0.0005  # the intermediate P&R grid
    top = layout.create_cell("efuse_otp_ctrl")
    top.shapes(layout.layer(80, 5)).insert(kdb.Box(0, 0, 200000, 200000))
    widths = {22: comp, 30: poly, **dict.fromkeys((34, 36, 42, 46, 81), metal)}
    for layer, width in widths.items():
        top.shapes(layout.layer(layer, 0)).insert(kdb.Box(0, 0, 2 * width, 200000))
    layout.write(str(path))


class DensityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.route = self.root / "routed.gds"

    def test_density_limits_and_cli_outputs(self):
        output = self.root / "filled.gds"
        report = self.root / "fill.json"
        cmd = [sys.executable, "-I", LAYOUT / "fill_partitions.py",
               "--input", self.route, "--output", output, "--report", report]
        # The native deck accepts exactly 25% and 70% COMP, 14% Poly2 and 30% metal.
        for comp in (25000, 70000):
            write_stream(self.route, comp=comp)
            subprocess.run(cmd, capture_output=True, check=True)
            self.assertTrue(json.loads(report.read_text())["all_pass"])
        good = (output.read_bytes(), report.read_bytes())

        for widths, failed_rule in [({"comp": 24999}, "DCF.1b"), ({"comp": 70001}, "DCF.1d"),
                                    ({"poly": 13999}, "PL.8"), ({"metal": 29999}, "M5.4")]:
            with self.subTest(widths=widths):
                write_stream(self.route, **widths)
                result = subprocess.run(cmd, capture_output=True, text=True)
                self.assertEqual(result.returncode, 5, result.stderr)
                self.assertIn(f"[{failed_rule}, FAIL]", result.stderr)
                self.assertEqual((output.read_bytes(), report.read_bytes()), good)

    def test_failed_fill_preserves_published_controller(self):
        layout = self.root / "layout"
        layout.mkdir()
        for script in ("pnr.sh", "dbu_export.py", "fill_partitions.py"):
            shutil.copy(LAYOUT / script, layout)
        # Replay P&R responses and run both geometry stages with the real interpreter.
        signoff = self.root / "signoff"
        signoff.mkdir()
        (signoff / "klt.sh").write_text(
            'klt() { cat route.json; }\nklt_python() { "$TEST_PYTHON" "$@"; }\n')
        netlist = self.root / "route.v"
        response = {"status": "ok", "stage_reached": "route", "power": {"pdn": True},
                    "route_drc_violation_count": 0, "antenna_violation_count": 0,
                    "gds_path": self.route.name, "verilog_path": netlist.name}
        (self.root / "route.json").write_text(json.dumps(response))
        netlist.write_text("module efuse_otp_ctrl; endmodule\n")
        write_stream(self.route)
        env = dict(os.environ, TEST_PYTHON=sys.executable)
        subprocess.run([layout / "pnr.sh"], env=env, capture_output=True, check=True)
        checksum_cmd = ["sha256sum", "-c", "efuse_otp_ctrl.gds.sha256"]
        subprocess.run(checksum_cmd, cwd=layout, check=True, capture_output=True)
        published = {name: (layout / name).read_bytes() for name in (
            "pnr-report.json", "fill-ctrl.report.json", "efuse_otp_ctrl.asbuilt.v",
            "efuse_otp_ctrl.gds", "efuse_otp_ctrl.gds.sha256")}
        files = set(layout.iterdir())

        write_stream(self.route, comp=24999)
        netlist.write_text("module new_candidate; endmodule\n")
        response["run"] = "new candidate"
        (self.root / "route.json").write_text(json.dumps(response))
        failed = subprocess.run([layout / "pnr.sh"], env=env, capture_output=True, text=True)
        self.assertEqual(failed.returncode, 5, failed.stderr)
        self.assertIn("24.999% [DCF.1b, FAIL]", failed.stderr)
        self.assertEqual(set(layout.iterdir()), files)
        for name, contents in published.items():
            self.assertEqual((layout / name).read_bytes(), contents, name)
        subprocess.run(checksum_cmd, cwd=layout, check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
