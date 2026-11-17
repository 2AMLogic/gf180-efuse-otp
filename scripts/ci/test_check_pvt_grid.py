import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "spec" / "efuse-otp.md"
EXTRACT = REPO / "signoff" / "item6-digital-spec.json"
STATEMENT = REPO / "signoff" / "item6-digital-statement.json"
CHECKER = REPO / "signoff" / "check-pvt-grid.sh"
ITEM6_CHECKER = REPO / "signoff" / "check-item6-digital.sh"
PDK_ENV = REPO / "sim" / "lib" / "pdk_env.sh"

SPEC_TEXT = SPEC.read_text(encoding="utf-8")
PDK_TEXT = PDK_ENV.read_text(encoding="utf-8")
ORIG_ROW = next(r["text"] for r in json.loads(EXTRACT.read_text(encoding="utf-8"))["rows"]
                if r["id"] == "pvt-corners")


def sub(text, old, new):
    assert old in text, "seed target missing: %r" % old
    return text.replace(old, new)


# Row amendments that keep the line verbatim in BOTH spec and extract, so the
# checker gets past its verbatim gate and the parse/compare under test runs.
ROW_NO_PROCESS = re.sub(r"Process (?:`[^`]+`(?:, )?)+; ", "", ORIG_ROW)
ROW_NO_TEMPS = re.sub(r"T = [^;]+ °C; ", "", ORIG_ROW)
ROW_UNCONVERTIBLE_TEMPS = re.sub(r"T = [^;]+ °C", "T = cold, warm, hot °C", ORIG_ROW)
ROW_SPACED_TRIPLETS = re.sub(
    r"\((\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)+) V\)",
    lambda m: "(" + m.group(1).replace("/", " / ") + " V)", ORIG_ROW)
ROW_ASCII_HYPHEN = sub(ORIG_ROW, "−40", "-40")
ROW_3V3_3DOT3 = sub(ORIG_ROW, "(2.97/3.30/3.63 V)", "(2.97/3.3/3.63 V)")
ROW_3V3_DRIFT = sub(ORIG_ROW, "(2.97/3.30/3.63 V)", "(2.97/3.30/3.7 V)")

PDK_PROCESSES_PERMUTED = sub(PDK_TEXT, '"typical","ff","ss","fs","sf"',
                             '"ff","typical","ss","fs","sf"')
PDK_TEMPS_DRIFT = sub(PDK_TEXT, "[-40,25,125]", "[-40,25,150]")
PDK_3V3_DRIFT = sub(PDK_TEXT, "[2.97,3.30,3.63]", "[2.97,3.30,3.7]")
PDK_3V3_NOT_JSON = sub(PDK_TEXT, "[2.97,3.30,3.63]", "[2.97 3.30]")
PDK_5V0_DRIFT = sub(PDK_TEXT, "[4.5,5.0,5.5]", "[4.5,5.0,5.6]")
PDK_5V0_UNSET = sub(PDK_TEXT, "PVT_SUPPLY_5V0='[4.5,5.0,5.5]'",
                    ": # seeded variant: constant intentionally left unset")


def make_tree(spec_row=None, extract_row=None, drop_pvt_row=False,
              pdk_env_text=None, rehash=False, with_item6=False):
    root = Path(tempfile.mkdtemp())
    for d in ("spec", "signoff", "sim/lib"):
        (root / d).mkdir(parents=True)
    shutil.copy2(CHECKER, root / "signoff" / CHECKER.name)
    if with_item6:
        shutil.copy2(ITEM6_CHECKER, root / "signoff" / ITEM6_CHECKER.name)
        shutil.copy2(STATEMENT, root / "signoff" / STATEMENT.name)
    spec_file = root / "spec" / SPEC.name
    spec_file.write_text(
        SPEC_TEXT if spec_row is None else sub(SPEC_TEXT, ORIG_ROW, spec_row),
        encoding="utf-8")
    ex = json.loads(EXTRACT.read_text(encoding="utf-8"))
    touched = False
    for r in ex["rows"]:
        if r["id"] != "pvt-corners":
            continue
        touched = True
        if drop_pvt_row:
            r["id"] = "pvt-corners-renamed"
        elif extract_row is not None:
            r["text"] = extract_row
    if touched or rehash:
        if rehash:
            ex["source"]["sha256"] = hashlib.sha256(spec_file.read_bytes()).hexdigest()
        (root / "signoff" / EXTRACT.name).write_text(
            json.dumps(ex, indent=1), encoding="utf-8")
    else:
        shutil.copy2(EXTRACT, root / "signoff" / EXTRACT.name)
    pdk_file = root / "sim" / "lib" / "pdk_env.sh"
    if pdk_env_text is None:
        shutil.copy2(PDK_ENV, pdk_file)
    else:
        pdk_file.write_text(pdk_env_text, encoding="utf-8")
    return root


class Test(unittest.TestCase):
    def tree(self, **kw):
        root = make_tree(**kw)
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        return root

    def bash_run(self, root, name):
        return subprocess.run(["bash", str(root / "signoff" / name)],
                              cwd=root, capture_output=True, text=True, timeout=60)

    def check(self, **kw):
        return self.bash_run(self.tree(**kw), CHECKER.name)

    def test_unmodified_tree_passes(self):
        p = self.check()
        self.assertEqual(p.returncode, 0)
        self.assertIn("OK:", p.stdout)

    def test_missing_pvt_row_rejected(self):
        p = self.check(drop_pvt_row=True)
        self.assertEqual(p.returncode, 1)
        self.assertIn("signoff/item6-digital-spec.json has no pvt-corners row", p.stderr)

    def test_row_not_verbatim_rejected(self):
        p = self.check(extract_row=ORIG_ROW + " ")
        self.assertEqual(p.returncode, 1)
        self.assertIn("no longer appears verbatim as a line of spec/efuse-otp.md", p.stderr)

    def test_unparseable_process_list_rejected(self):
        p = self.check(spec_row=ROW_NO_PROCESS, extract_row=ROW_NO_PROCESS)
        self.assertEqual(p.returncode, 1)
        self.assertIn("cannot parse the process list from the pvt-corners row", p.stderr)

    def test_unparseable_temperature_list_rejected(self):
        p = self.check(spec_row=ROW_NO_TEMPS, extract_row=ROW_NO_TEMPS)
        self.assertEqual(p.returncode, 1)
        self.assertIn("cannot parse the temperature list from the pvt-corners row", p.stderr)

    def test_unconvertible_temperature_list_rejected(self):
        # The T = ... °C span matches the regex but float() raises ValueError:
        # the sibling reason of test_unparseable_temperature_list_rejected.
        self.assertNotEqual(ROW_UNCONVERTIBLE_TEMPS, ORIG_ROW)
        p = self.check(spec_row=ROW_UNCONVERTIBLE_TEMPS,
                       extract_row=ROW_UNCONVERTIBLE_TEMPS)
        self.assertEqual(p.returncode, 1)
        self.assertIn("cannot parse the temperature list 'cold, warm, hot' "
                      "from the pvt-corners row", p.stderr)

    def test_unparseable_supply_triplets_rejected(self):
        self.assertNotEqual(ROW_SPACED_TRIPLETS, ORIG_ROW)
        p = self.check(spec_row=ROW_SPACED_TRIPLETS, extract_row=ROW_SPACED_TRIPLETS)
        self.assertEqual(p.returncode, 1)
        self.assertIn("expected exactly two '(a/b/c V)' supply triplets", p.stderr)

    def test_missing_constant_rejected(self):
        # The checker's `could not source` path is unreachable by deleting
        # sim/lib/pdk_env.sh (a failed source still yields the surviving
        # constants, so the four-values reason reports instead); the seed for
        # this reason is an unset constant.
        p = self.check(pdk_env_text=PDK_5V0_UNSET)
        self.assertEqual(p.returncode, 1)
        self.assertIn("did not yield four non-empty PVT_* values", p.stderr)

    def test_non_json_constant_rejected(self):
        p = self.check(pdk_env_text=PDK_3V3_NOT_JSON)
        self.assertEqual(p.returncode, 1)
        self.assertIn("PVT_SUPPLY_3V3 from sim/lib/pdk_env.sh is not JSON", p.stderr)

    def test_processes_axis_disagrees(self):
        p = self.check(pdk_env_text=PDK_PROCESSES_PERMUTED)
        self.assertEqual(p.returncode, 1)
        self.assertIn("processes axis disagrees", p.stderr)

    def test_temperatures_axis_disagrees(self):
        p = self.check(pdk_env_text=PDK_TEMPS_DRIFT)
        self.assertEqual(p.returncode, 1)
        self.assertIn("temperatures axis disagrees", p.stderr)

    def test_supply_3v3_axis_disagrees(self):
        p = self.check(pdk_env_text=PDK_3V3_DRIFT)
        self.assertEqual(p.returncode, 1)
        self.assertIn("logic/sense supply 3.3 V axis disagrees", p.stderr)

    def test_supply_5v0_axis_disagrees(self):
        p = self.check(pdk_env_text=PDK_5V0_DRIFT)
        self.assertEqual(p.returncode, 1)
        self.assertIn("program supply 5.0 V axis disagrees", p.stderr)

    def test_ascii_hyphen_normalization_passes(self):
        self.assertNotEqual(ROW_ASCII_HYPHEN, ORIG_ROW)
        p = self.check(spec_row=ROW_ASCII_HYPHEN, extract_row=ROW_ASCII_HYPHEN)
        self.assertEqual(p.returncode, 0)

    def test_3v3_decimal_normalization_passes(self):
        self.assertNotEqual(ROW_3V3_3DOT3, ORIG_ROW)
        p = self.check(spec_row=ROW_3V3_3DOT3, extract_row=ROW_3V3_3DOT3)
        self.assertEqual(p.returncode, 0)

    def test_cross_checker_discrimination(self):
        # The spec row drifted and the extract was regenerated (re-hashed), so
        # check-item6-digital.sh passes and only check-pvt-grid.sh catches it.
        root = self.tree(spec_row=ROW_3V3_DRIFT, extract_row=ROW_3V3_DRIFT,
                         rehash=True, with_item6=True)
        item6 = self.bash_run(root, ITEM6_CHECKER.name)
        pvt = self.bash_run(root, CHECKER.name)
        self.assertEqual(item6.returncode, 0)
        self.assertEqual(pvt.returncode, 1)
        self.assertIn("logic/sense supply 3.3 V axis disagrees", pvt.stderr)


if __name__ == "__main__":
    unittest.main()
