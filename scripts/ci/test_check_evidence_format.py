import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import check_evidence_format as cef

GOOD = {"pdk_revision": "abc123", "tool_versions": {"ngspice": "44"},
        "corners": ["tt"], "netlist": "sim/x/netlist.spice"}
# The payload shape of the 11 grandfathered directories: valid, but without
# the two fields their benches only started emitting after the operator
# ruling on #118.
LEGACY_PAYLOAD = {"pdk_revision": "abc123", "netlist": "sim/x/netlist.spice"}
# One real entry of the checker's frozen list, and the same stamp planted
# under a different bench: the exemption matches the exact directory, so a
# look-alike path elsewhere is not exempt.
LEGACY_REL = "sim/corner-verification/records/20261030T230649Z-f6eeac7"
LEGACY_STAMP = LEGACY_REL.split("/")[-1]
LOOKALIKE_REL = "sim/sense-margin/records/" + LEGACY_STAMP


def write(root, rel, text):
    p = root / Path(rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def make_tree(case, record=None, at="sim/t/records/20260101T000000Z-deadbee",
              extra=()):
    """Temp root with every evidence README plus optional files.

    `record` is written as record.json at `at` (a record directory path);
    `extra` is an iterable of (relative path, text) written as-is, for flat
    JSON at the pre-#118 depth, klt set reports, and other non-record files.
    """
    root = Path(tempfile.mkdtemp())
    case.addCleanup(shutil.rmtree, root, ignore_errors=True)
    for d in cef.EVIDENCE_DIRS:
        (root / d).mkdir()
        (root / d / "README.md").write_text("x\n")
    for rel, text in extra:
        write(root, rel, text)
    if record is not None:
        write(root, Path(at) / "record.json", json.dumps(record))
    return root


class Test(unittest.TestCase):
    def run_check(self, capture=False, **kw):
        root = make_tree(self, **kw)
        if not capture:
            return cef.main(["--root", str(root)])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cef.main(["--root", str(root)])
        return rc, out.getvalue()

    def test_clean_with_record(self):
        self.assertEqual(self.run_check(record=GOOD), 0)

    def test_record_count_is_reported(self):
        rc1, out1 = self.run_check(capture=True, record=GOOD)
        self.assertEqual(rc1, 0)
        self.assertIn("1 sim record(s)", out1)
        rc2, out2 = self.run_check(
            capture=True,
            record=GOOD, at="sim/t/records/20260101T000001Z-deadbee",
            extra=[("sim/u/records/20260101T000002Z-deadbee/record.json",
                    json.dumps(GOOD))])
        self.assertEqual(rc2, 0)
        self.assertIn("2 sim record(s)", out2)

    def test_no_records_fails(self):
        """A repo with all READMEs but zero matched records is a failure:
        zero matches is the discovery defect this check exists to catch."""
        rc, out = self.run_check(capture=True)
        self.assertNotEqual(rc, 0)
        self.assertIn("FAIL", out)

    def test_flat_json_at_the_old_depth_does_not_satisfy_the_check(self):
        rc, out = self.run_check(
            capture=True, extra=[("sim/t/records/r.json", json.dumps(GOOD))])
        self.assertNotEqual(rc, 0)
        self.assertIn("FAIL", out)

    def test_klt_reports_alone_do_not_satisfy_the_check(self):
        report = json.dumps({"environment": {"ngspice_binary": "/abs/ngspice"}})
        rc, out = self.run_check(
            capture=True,
            extra=[("sim/t/records/20260101T000000Z-deadbee/sets/"
                    "cell_r200_w20/report.json", report)])
        self.assertNotEqual(rc, 0)
        self.assertIn("FAIL", out)

    def test_record_alongside_klt_reports_counts_only_the_record(self):
        """klt's own set reports carry absolute worktree paths by design;
        only the per-bench record.json is held to the format."""
        report = json.dumps({"environment": {"ngspice_binary": "/abs/ngspice"}})
        rc = self.run_check(
            record=GOOD,
            extra=[("sim/t/records/20260101T000000Z-deadbee/sets/"
                    "cell_r200_w20/report.json", report)])
        self.assertEqual(rc, 0)

    def test_missing_readme_rejected(self):
        root = make_tree(self, record=GOOD)
        (root / "rtl" / "README.md").unlink()
        self.assertNotEqual(cef.main(["--root", str(root)]), 0)

    def test_missing_pdk_revision_rejected(self):
        bad = {k: v for k, v in GOOD.items() if k != "pdk_revision"}
        self.assertNotEqual(self.run_check(record=bad), 0)

    def test_each_required_field_missing_or_empty_rejected(self):
        for field in cef.REQUIRED_FIELDS:
            for bad_value in (None, "", [], {}):
                with self.subTest(field=field, value=bad_value):
                    bad = {**GOOD, field: bad_value}
                    self.assertNotEqual(self.run_check(record=bad), 0)

    def test_absolute_path_rejected(self):
        self.assertNotEqual(self.run_check(record={**GOOD, "netlist": "/home/u/n.spice"}), 0)

    def test_parent_traversal_rejected(self):
        self.assertNotEqual(self.run_check(record={**GOOD, "netlist": "../n.spice"}), 0)

    def test_unsafe_nested_path_rejected(self):
        bad = {**GOOD, "measurements": {"log": "C:\\ngspice\\x.log"}}
        self.assertNotEqual(self.run_check(record=bad), 0)

    def test_malformed_json_rejected(self):
        root = make_tree(self)
        write(root, "sim/t/records/20260101T000000Z-deadbee/record.json", "{")
        self.assertNotEqual(cef.main(["--root", str(root)]), 0)

    def test_non_object_top_level_rejected(self):
        root = make_tree(self)
        write(root, "sim/t/records/20260101T000000Z-deadbee/record.json", "[1]")
        self.assertNotEqual(cef.main(["--root", str(root)]), 0)

    def test_tilde_and_drive_rejected(self):
        self.assertIsNotNone(cef.bad_path("~/n"))
        self.assertIsNotNone(cef.bad_path("C:\\n"))
        self.assertIsNone(cef.bad_path("https://example.org/a"))

    # -- the #118 operator ruling: 11 committed directories are exempt from
    # exactly the two fields they never carried; everything else is not.

    def test_legacy_list_is_well_shaped_and_only_exempts_two_fields(self):
        self.assertEqual(cef.LEGACY_EXEMPT_FIELDS,
                         ("tool_versions", "corners"))
        self.assertEqual(len(cef.LEGACY_DIRS), 11)
        for d in cef.LEGACY_DIRS:
            self.assertRegex(d, r"^sim/[^/]+/records/[^/]+$")

    def test_exact_legacy_path_accepts_the_two_omissions(self):
        self.assertEqual(self.run_check(record=LEGACY_PAYLOAD, at=LEGACY_REL), 0)

    def test_legacy_payload_at_a_new_stamp_reports_both_omissions(self):
        rc, out = self.run_check(
            capture=True, record=LEGACY_PAYLOAD,
            at="sim/corner-verification/records/20260101T000000Z-deadbee")
        self.assertNotEqual(rc, 0)
        self.assertIn("missing required field 'tool_versions'", out)
        self.assertIn("missing required field 'corners'", out)

    def test_legacy_payload_under_another_bench_reports_both_omissions(self):
        rc, out = self.run_check(capture=True, record=LEGACY_PAYLOAD,
                                 at=LOOKALIKE_REL)
        self.assertNotEqual(rc, 0)
        self.assertIn("missing required field 'tool_versions'", out)
        self.assertIn("missing required field 'corners'", out)

    def test_legacy_path_still_needs_pdk_revision(self):
        bad = {k: v for k, v in LEGACY_PAYLOAD.items() if k != "pdk_revision"}
        self.assertNotEqual(self.run_check(record=bad, at=LEGACY_REL), 0)

    def test_legacy_path_still_rejects_malformed_json(self):
        root = make_tree(self)
        write(root, Path(LEGACY_REL) / "record.json", "{")
        self.assertNotEqual(cef.main(["--root", str(root)]), 0)

    def test_legacy_path_still_rejects_unsafe_paths(self):
        bad = {**LEGACY_PAYLOAD, "netlist": "/home/u/n.spice"}
        self.assertNotEqual(self.run_check(record=bad, at=LEGACY_REL), 0)


if __name__ == "__main__":
    unittest.main()
