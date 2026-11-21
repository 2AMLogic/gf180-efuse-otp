import hashlib
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import check_report_inputs as cri

REPO_ROOT = Path(__file__).resolve().parents[2]

ARRAY = b"array gds bytes\n"
CTRL = b"ctrl gds bytes\n"  # shared by the drc-ctrl and lvs-ctrl shapes
NETLIST = b"module efuse_otp_ctrl;\nendmodule\n"
# The historical dff2f9c-era drift: a report recording e9786490... beside a
# stream hashing 186be6b6.... Seeded here as a tmp tree, never by editing a
# committed artifact.
DRIFT = "sha256:" + "e9786490" + "0" * 56


def sha(data):
    return hashlib.sha256(data).hexdigest()


def report(role, field, stream_path, data, scope="repo", recorded=None,
           extra=None):
    """A layout report naming its input stream the way the generators do."""
    node = {"provenance": {"input": {
        "role": role,
        "content_hash": recorded if recorded is not None else "sha256:" + sha(data),
    }}}
    if field is not None:
        node[field] = {"path": stream_path, "scope": scope}
    if extra:
        node.update(extra)
    return node


def clean_tree():
    """The ten gated layout/ reports plus the skipped one, all matching."""
    return {
        "layout/efuse_otp_array.gds": ARRAY,
        "layout/efuse_otp_ctrl.gds": CTRL,
        "rtl/efuse_otp_ctrl.gl.v": NETLIST,
        "layout/drc-array.report.json":
            report("layout", "file", "layout/efuse_otp_array.gds", ARRAY),
        "layout/drc-ctrl.report.json":
            report("layout", "file", "layout/efuse_otp_ctrl.gds", CTRL),
        # The routed analog cells (efuse_ls, efuse_rowdrv, efuse_coldrv): each
        # DRC'd and LVS'd as a top of the analog stream, so the report names
        # efuse_otp_array.gds, not a per-cell stream.
        **{f"layout/{kind}-{cell}.report.json":
           report("layout", "file", "layout/efuse_otp_array.gds", ARRAY)
           for kind in ("drc", "lvs") for cell in ("ls", "rowdrv", "coldrv")},
        # The lvs-ctrl shape: role layout, resolved via .layout.path, no .file.
        "layout/lvs-ctrl.report.json":
            report("layout", "layout", "layout/efuse_otp_ctrl.gds", CTRL),
        # The pnr-report shape: stream outside layout/, plus the def_path /
        # gds_path / verilog_path fields a heuristic would mis-follow.
        "layout/pnr-report.json":
            report("netlist", "netlist", "rtl/efuse_otp_ctrl.gl.v", NETLIST,
                   extra={"def_path": {"path": "layout/.klt/place-and-route/x.def",
                                       "scope": "repo"},
                          "gds_path": {"path": "layout/.klt/place-and-route/x.gds",
                                       "scope": "repo"},
                          "verilog_path": {"path": "layout/.klt/place-and-route/x.v",
                                           "scope": "repo"}}),
        # The efuse_otp_array.report.json shape: no provenance block at all.
        "layout/efuse_otp_array.report.json":
            {"array": [], "bbox_um": [0, 0, 1, 1], "top_cell": "efuse_otp_array"},
    }


def make_tree(case, files):
    root = Path(tempfile.mkdtemp())
    case.addCleanup(shutil.rmtree, root, ignore_errors=True)
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, (bytes, bytearray)):
            p.write_bytes(content)
        elif isinstance(content, str):
            p.write_text(content)
        else:
            p.write_text(json.dumps(content))
    return root


class Test(unittest.TestCase):
    def run_main(self, files, args=()):
        out = StringIO()
        with redirect_stdout(out):
            rc = cri.main(["--root", str(make_tree(self, files)), *args])
        return rc, out.getvalue()

    def test_clean_tree_passes(self):
        rc, out = self.run_main(clean_tree())
        self.assertEqual(rc, 0)
        self.assertIn("10 report input hash(es) match", out)
        self.assertIn("1 skipped", out)

    def test_empty_tree_passes_vacuously(self):
        # An empty tree gates nothing, so main() takes its vacuous-pass
        # branch and check:ci is green with nothing seeded. No gated pair
        # is exercised here -- the real-tree pin lives in
        # test_real_tree_gates_twelve_reports.
        rc, out = self.run_main({})
        self.assertEqual(rc, 0, out)
        self.assertIn("passes vacuously", out)

    def test_real_tree_gates_twelve_reports(self):
        problems, gated, skipped = cri.check(REPO_ROOT)
        self.assertEqual(problems, [])
        self.assertEqual(gated, 12)
        self.assertEqual(skipped, 1)

    def test_recorded_hash_mismatch_fails(self):
        files = clean_tree()
        files["layout/drc-array.report.json"] = report(
            "layout", "file", "layout/efuse_otp_array.gds", ARRAY,
            recorded=DRIFT)
        rc, out = self.run_main(files)
        self.assertEqual(rc, 1)
        self.assertIn("layout/drc-array.report.json", out)
        self.assertIn("e9786490", out)
        self.assertIn("layout/efuse_otp_array.gds", out)
        self.assertIn(sha(ARRAY), out)

    def test_mismatch_fails_via_layout_path(self):
        # Prove the lvs-ctrl shape is gated, not skipped.
        files = clean_tree()
        files["layout/lvs-ctrl.report.json"] = report(
            "layout", "layout", "layout/efuse_otp_ctrl.gds", CTRL,
            recorded=DRIFT)
        rc, out = self.run_main(files)
        self.assertEqual(rc, 1)
        self.assertIn("layout/lvs-ctrl.report.json", out)

    def test_unknown_role_fails(self):
        files = clean_tree()
        files["layout/drc-array.report.json"] = report(
            "spice", "file", "layout/efuse_otp_array.gds", ARRAY)
        rc, out = self.run_main(files)
        self.assertEqual(rc, 1)
        self.assertIn("unknown provenance.input.role 'spice'", out)

    def test_missing_role_field_fails(self):
        # The controller-sta shape: role layout, no .file, no .layout, but a
        # def_path into the uncommitted layout/.klt/ tree. Must fail rather
        # than silently follow def_path.
        files = clean_tree()
        files["layout/drc-array.report.json"] = report(
            "layout", None, None, ARRAY,
            extra={"def_path": {"path": "layout/.klt/place-and-route/x.def",
                                "scope": "repo"}})
        rc, out = self.run_main(files)
        self.assertEqual(rc, 1)
        self.assertIn("none of .file.path or .layout.path carries a string path", out)
        # The def_path was never followed: no .klt path anywhere in the output.
        self.assertNotIn(".klt", out)

    def test_non_string_path_fails(self):
        files = clean_tree()
        bad = report("layout", "file", "layout/efuse_otp_array.gds", ARRAY)
        bad["file"]["path"] = 123
        files["layout/drc-array.report.json"] = bad
        rc, out = self.run_main(files)
        self.assertEqual(rc, 1)
        self.assertIn("none of .file.path or .layout.path carries a string path", out)

    def test_non_repo_scope_fails(self):
        files = clean_tree()
        files["layout/drc-array.report.json"] = report(
            "layout", "file", "layout/efuse_otp_array.gds", ARRAY, scope="work")
        rc, out = self.run_main(files)
        self.assertEqual(rc, 1)
        self.assertIn("scope 'work', not \"repo\"", out)

    def test_absent_stream_file_fails(self):
        files = clean_tree()
        files["layout/drc-array.report.json"] = report(
            "layout", "file", "layout/ghost.gds", ARRAY)
        rc, out = self.run_main(files)
        self.assertEqual(rc, 1)
        self.assertIn("layout/ghost.gds", out)
        self.assertIn("not present in the tree", out)

    def test_no_provenance_skipped(self):
        problems, gated, skipped = cri.check(make_tree(self, clean_tree()))
        self.assertEqual(problems, [])
        self.assertEqual(gated, 10)
        self.assertEqual(skipped, 1)

    def test_hash_without_prefix_matches(self):
        files = clean_tree()
        files["layout/drc-array.report.json"] = report(
            "layout", "file", "layout/efuse_otp_array.gds", ARRAY,
            recorded=sha(ARRAY))
        rc, out = self.run_main(files)
        self.assertEqual(rc, 0, out)

    def test_unparseable_report_is_defect(self):
        files = clean_tree()
        files["layout/drc-array.report.json"] = "{not json"
        rc, out = self.run_main(files)
        self.assertEqual(rc, 1)
        self.assertIn("unparseable JSON", out)

    def test_non_object_report_is_defect(self):
        files = clean_tree()
        files["layout/drc-array.report.json"] = "[]"
        rc, out = self.run_main(files)
        self.assertEqual(rc, 1)
        self.assertIn("top level must be a JSON object", out)

    def test_stream_outside_layout_gated_normally(self):
        # The glob bounds which reports are read, never which streams may be
        # named: pnr-report names rtl/... and must be checked like the rest.
        files = clean_tree()
        files["layout/pnr-report.json"] = report(
            "netlist", "netlist", "rtl/efuse_otp_ctrl.gl.v", NETLIST,
            recorded=DRIFT)
        rc, out = self.run_main(files)
        self.assertEqual(rc, 1)
        self.assertIn("layout/pnr-report.json", out)
        self.assertIn("rtl/efuse_otp_ctrl.gl.v", out)


if __name__ == "__main__":
    unittest.main()
