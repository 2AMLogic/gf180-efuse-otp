import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import check_readme_enumeration as cre


def write(root, rel, content):
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)


def pkg(check_ci):
    return json.dumps({"name": "fixture", "private": True,
                       "scripts": {"check:ci": check_ci}})


def readme(paragraph):
    return ("# Fixture repo\n\n"
            "Intro paragraph that must be skipped.\n\n"
            + paragraph + "\n\n"
            "## Repo layout\n")


PARA_CLEAN = """\
`npm run -s check:ci` is the local pre-flight: the checker self-tests
(`scripts/ci/test_*.py`), the evidence-format check
(`scripts/ci/check_evidence_format.py`), the grid binding check
(`signoff/check-pvt-grid.sh`) and the loader self-test
(`sim/lib/test_bench_record.py`). The workflow runs every check in that
list, as individually named steps of the `harness` job."""

SELF_TEST_TERM = ("(cd scripts/ci && python3 -I -m unittest discover -s . "
                  "-p 'test_*.py' -v)")
CLEAN_CHAIN = " && ".join([
    SELF_TEST_TERM,
    "python3 scripts/ci/check_evidence_format.py",
    "signoff/check-pvt-grid.sh",
    "python3 -I sim/lib/test_bench_record.py",
    "echo 'check:ci OK -- hermetic checks only: this does NOT run the CI steps "
    "that need an EDA tool (verification/run.sh), so a green check:ci is not a "
    "prediction that CI will pass.'",
])


def make_fixture(root, check_ci=CLEAN_CHAIN, paragraph=PARA_CLEAN):
    write(root, "package.json", pkg(check_ci))
    write(root, "README.md", readme(paragraph))
    return root


class Test(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def run_check(self, check_ci=CLEAN_CHAIN, paragraph=PARA_CLEAN):
        make_fixture(self.root, check_ci, paragraph)
        return cre.check(self.root / "package.json", self.root / "README.md")

    def run_main(self, check_ci=CLEAN_CHAIN, paragraph=PARA_CLEAN,
                 readme_text=None):
        make_fixture(self.root, check_ci, paragraph)
        if readme_text is not None:
            write(self.root, "README.md", readme_text)
        out = StringIO()
        with redirect_stdout(out):
            code = cre.main(["--package", str(self.root / "package.json"),
                             "--readme", str(self.root / "README.md")])
        return code, out.getvalue()

    # -- the clean enumeration ----------------------------------------------

    def test_clean_chain_enumerates_every_term(self):
        problems, stats = self.run_check()
        self.assertEqual([m for m, _ in problems], [])
        self.assertEqual(stats["terms"], 5)
        self.assertEqual(stats["matched"], 4)
        self.assertEqual(stats["echo_skipped"], 1)

    def test_clean_run_exit_0_and_ok_line(self):
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("OK:", out)
        self.assertIn("4 enumerated", out)
        self.assertIn("0 unenumerated", out)

    # -- the seeded-bad cases (the drift this checker exists for) ------------

    def test_seeded_missing_path_is_rejected(self):
        seeded = PARA_CLEAN.replace("(`signoff/check-pvt-grid.sh`)",
                                    "(the grid binding check)")
        problems, stats = self.run_check(paragraph=seeded)
        msgs = [m for m, _ in problems]
        self.assertEqual(len(msgs), 1)
        self.assertIn("signoff/check-pvt-grid.sh", msgs[0])
        self.assertIn("not enumerated", msgs[0])
        self.assertEqual(stats["matched"], 3)
        code, out = self.run_main(paragraph=seeded)
        self.assertEqual(code, 1)
        self.assertIn("FAIL:", out)
        self.assertIn("signoff/check-pvt-grid.sh", out)

    def test_unittest_subshell_term_needs_both_keys(self):
        seeded = PARA_CLEAN.replace("(`scripts/ci/test_*.py`)",
                                    "(the checker self-tests)")
        problems, _ = self.run_check(paragraph=seeded)
        msgs = [m for m, _ in problems]
        self.assertEqual(len(msgs), 1)
        # the drift is named against the whole term, not just one key
        self.assertIn("discover", msgs[0])
        self.assertIn("'test_*.py'", msgs[0])

    def test_only_the_paragraph_is_searched(self):
        # the path removed from the paragraph but present in another
        # paragraph must still fail: the binding is to THIS paragraph.
        drifted = ("# Fixture repo\n\n"
                   "Elsewhere we mention `signoff/check-pvt-grid.sh`.\n\n"
                   + PARA_CLEAN.replace("(`signoff/check-pvt-grid.sh`)",
                                        "(the grid binding check)") + "\n\n"
                   "## Repo layout\n")
        code, out = self.run_main(readme_text=drifted)
        self.assertEqual(code, 1)
        self.assertIn("signoff/check-pvt-grid.sh", out)

    # -- fail-closed structural cases ----------------------------------------

    def test_missing_paragraph_fails_closed(self):
        code, out = self.run_main(
            readme_text="# Fixture repo\n\nNo enumeration here.\n")
        self.assertEqual(code, 1)
        self.assertIn("no paragraph opens with", out)
        self.assertIn("`npm run -s check:ci`", out)

    def test_unreadable_package_fails_closed(self):
        make_fixture(self.root)
        (self.root / "package.json").unlink()
        out = StringIO()
        with redirect_stdout(out):
            code = cre.main(["--package", str(self.root / "package.json"),
                             "--readme", str(self.root / "README.md")])
        self.assertEqual(code, 1)
        self.assertIn("unreadable or unparseable", out.getvalue())

    def test_stray_and_chain_fails_closed(self):
        problems, _ = self.run_check(check_ci="python3 x.py && && echo hi")
        msgs = [m for m, _ in problems]
        self.assertEqual(len(msgs), 1)
        self.assertIn("empty term", msgs[0])

    def test_untokenizable_term_fails_closed(self):
        problems, _ = self.run_check(
            check_ci="python3 scripts/ci/check_evidence_format.py "
                     "&& echo 'unterminated")
        msgs = [m for m, _ in problems]
        self.assertTrue(any("does not shell-tokenize" in m for m in msgs))

    # -- the real tree --------------------------------------------------------

    def test_real_tree_enumerates_every_term(self):
        root = Path(__file__).resolve().parents[2]
        problems, stats = cre.check(root / "package.json",
                                    root / "README.md")
        self.assertEqual([m for m, _ in problems], [])
        self.assertEqual(stats["echo_skipped"], 1)
        self.assertEqual(stats["matched"], stats["terms"] - 1)


if __name__ == "__main__":
    unittest.main()
