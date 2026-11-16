import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "spec" / "efuse-otp.md"
EXTRACT = REPO / "signoff" / "item6-digital-spec.json"
STATEMENT = REPO / "signoff" / "item6-digital-statement.json"
CHECKER = REPO / "signoff" / "check-item6-digital.sh"


def make_tree(spec_text=None, extract=None, statement=None):
    root = Path(tempfile.mkdtemp())
    (root / "spec").mkdir()
    (root / "signoff").mkdir()
    shutil.copy2(CHECKER, root / "signoff" / CHECKER.name)
    if spec_text is None:
        shutil.copy2(SPEC, root / "spec" / SPEC.name)
    else:
        (root / "spec" / SPEC.name).write_text(spec_text, encoding="utf-8")
    for src, obj in ((EXTRACT, extract), (STATEMENT, statement)):
        dst = root / "signoff" / src.name
        if obj is None:
            shutil.copy2(src, dst)
        else:
            dst.write_text(json.dumps(obj, indent=1), encoding="utf-8")
    return root


class Test(unittest.TestCase):
    def check(self, **kw):
        root = make_tree(**kw)
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        return subprocess.run(["bash", str(root / "signoff" / CHECKER.name)],
                              cwd=root, capture_output=True, text=True, timeout=60)

    def test_unmodified_tree_passes(self):
        p = self.check()
        self.assertEqual(p.returncode, 0)
        self.assertIn("OK:", p.stdout)

    def test_wrong_source_file_rejected(self):
        ex = json.loads(EXTRACT.read_text(encoding="utf-8"))
        ex["source"]["file"] = "elsewhere.md"
        p = self.check(extract=ex)
        self.assertEqual(p.returncode, 1)
        self.assertIn("extract source.file is not spec/efuse-otp.md", p.stderr)

    def test_stale_sha_rejected(self):
        spec_text = SPEC.read_text(encoding="utf-8") + "\nappended after the fact\n"
        p = self.check(spec_text=spec_text)
        self.assertEqual(p.returncode, 1)
        self.assertIn("spec/efuse-otp.md changed: extract source.sha256 is stale", p.stderr)

    def test_unratified_spec_rejected(self):
        spec_text = SPEC.read_text(encoding="utf-8").replace(
            "Status: **ratified**", "Status: draft")
        p = self.check(spec_text=spec_text)
        self.assertEqual(p.returncode, 1)
        self.assertIn("spec/efuse-otp.md no longer declares itself ratified", p.stderr)

    def test_row_drift_rejected(self):
        ex = json.loads(EXTRACT.read_text(encoding="utf-8"))
        ex["rows"][0]["text"] += " "
        p = self.check(extract=ex)
        self.assertEqual(p.returncode, 1)
        self.assertIn("'array' no longer matches a line of the spec", p.stderr)

    def test_id_mismatch_rejected(self):
        st = json.loads(STATEMENT.read_text(encoding="utf-8"))
        st["rows"] = st["rows"][:-1]
        p = self.check(statement=st)
        self.assertEqual(p.returncode, 1)
        self.assertIn("extract and statement ids differ", p.stderr)


if __name__ == "__main__":
    unittest.main()
