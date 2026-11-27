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
        route_def = self.root / "route.def"
        route_def.write_text("DESIGN efuse_otp_ctrl ;\nEND DESIGN\n")
        netlist = self.root / "route.v"
        response = {"status": "ok", "stage_reached": "route", "power": {"pdn": True},
                    "route_drc_violation_count": 0, "antenna_violation_count": 0,
                    "def_path": {"path": route_def.name, "scope": "repo"},
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
            "efuse_otp_ctrl.def", "efuse_otp_ctrl.gds", "efuse_otp_ctrl.gds.sha256")}
        self.assertEqual(published["efuse_otp_ctrl.def"], route_def.read_bytes())
        files = set(layout.iterdir())

        write_stream(self.route, comp=24999)
        route_def.write_text("DESIGN new_candidate ;\nEND DESIGN\n")
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

    def test_metal2_third_pass_reaches_floor(self):
        """Bands too narrow for a 3 um square: only Metal2's third pass reaches M2.4 (#365)."""
        sys.path.insert(0, str(LAYOUT))
        import fill_partitions as fp
        layout = kdb.Layout()
        layout.dbu = 0.0005
        top = layout.create_cell("efuse_otp_array")
        # 2.1 um stripes on a 9 um pitch across a 400 um die: each keeps 2 um
        # (DM.n.3), so a 2.9 um band stays free between neighbours and none at
        # the top or bottom edge. The die is large enough to stay under DCF.1d.
        for k in range(45):
            top.shapes(layout.layer(36, 0)).insert(
                kdb.Box(0, 4000 + 18000 * k, 800000, 8200 + 18000 * k))
        layout.write(str(self.route))
        report = self.root / "fill.json"
        cmd = [sys.executable, "-I", LAYOUT / "fill_partitions.py", "--input", self.route,
               "--output", self.root / "filled.gds", "--report", report]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        written = json.loads(report.read_text())
        self.assertEqual(written["pattern_um"]["metal_third_square"], 2.0)
        self.assertEqual(written["pattern_um"]["metal_third_pitch"], 3.0)
        self.assertEqual(written["pattern_um"]["metal_third_layers"], ["Metal2"])
        metal2 = next(row for row in written["layers"] if row["name"] == "Metal2")
        self.assertGreaterEqual(metal2["total_pct"], 30)
        # The first two passes alone cannot get there: no 6 um or 3 um square fits a band.
        ly = kdb.Layout()
        ly.read(str(self.route))
        cell = ly.cell("efuse_otp_array")
        ext = kdb.Region(cell.bbox())
        halos_r = fp.halos(ly, cell, ly.dbu, [(fp.METALS[2], fp.METAL_SPACE_UM)], kdb.Region())
        drawn = fp.region(ly, cell, fp.METALS[2]).area()
        two = fp.fill_class(ext, halos_r, ly.dbu, fp.METAL_GAP, fp.metal_passes(2)[:2]).area()
        three = fp.fill_class(ext, halos_r, ly.dbu, fp.METAL_GAP, fp.metal_passes(2)).area()
        self.assertLess(drawn + two, 0.30 * ext.area())
        self.assertGreaterEqual(drawn + three, 0.30 * ext.area())
        self.assertEqual([len(fp.metal_passes(n)) for n in fp.METALS], [2, 3, 2, 2, 2])


if __name__ == "__main__":
    unittest.main()
