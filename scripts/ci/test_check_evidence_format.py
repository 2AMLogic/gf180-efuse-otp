import json
import shutil
import tempfile
import unittest
from pathlib import Path

import check_evidence_format as cef

GOOD = {"pdk_revision": "abc123", "tool_versions": {"ngspice": "44"},
        "corners": ["tt"], "netlist": "sim/x/netlist.spice"}


def make_tree(case, record=None, drop_readme=None):
    root = Path(tempfile.mkdtemp())
    case.addCleanup(shutil.rmtree, root, ignore_errors=True)
    for d in cef.EVIDENCE_DIRS:
        (root / d).mkdir()
        if d != drop_readme:
            (root / d / "README.md").write_text("x\n")
    if record is not None:
        rd = root / "sim" / "t" / "records"
        rd.mkdir(parents=True)
        (rd / "r.json").write_text(json.dumps(record))
    return root


class Test(unittest.TestCase):
    def run_check(self, **kw):
        return cef.main(["--root", str(make_tree(self, **kw))])

    def test_clean_without_records(self):
        self.assertEqual(self.run_check(), 0)

    def test_clean_with_record(self):
        self.assertEqual(self.run_check(record=GOOD), 0)

    def test_missing_readme_rejected(self):
        self.assertNotEqual(self.run_check(drop_readme="rtl"), 0)

    def test_missing_pdk_revision_rejected(self):
        bad = {k: v for k, v in GOOD.items() if k != "pdk_revision"}
        self.assertNotEqual(self.run_check(record=bad), 0)

    def test_absolute_path_rejected(self):
        self.assertNotEqual(self.run_check(record={**GOOD, "netlist": "/home/u/n.spice"}), 0)

    def test_parent_traversal_rejected(self):
        self.assertNotEqual(self.run_check(record={**GOOD, "netlist": "../n.spice"}), 0)

    def test_tilde_and_drive_rejected(self):
        self.assertIsNotNone(cef.bad_path("~/n"))
        self.assertIsNotNone(cef.bad_path("C:\\n"))
        self.assertIsNone(cef.bad_path("https://example.org/a"))


if __name__ == "__main__":
    unittest.main()
