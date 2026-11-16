import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import check_ci_yml_binding as ccb


def write(root, rel, content):
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)


def pkg(check_ci):
    return json.dumps({"name": "fixture", "private": True,
                       "scripts": {"check:ci": check_ci}})


CI_CLEAN = """\
name: ci
on:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  controller:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Bench
        run: verification/run.sh
  harness:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Checker self-tests
        working-directory: scripts/ci
        run: python3 -I -m unittest discover -s . -p 'test_*.py' -v
      - name: Evidence format
        # a stale YAML-comment mention must not satisfy a term
        run: python3 scripts/ci/check_evidence_format.py
      - name: Multiline binding
        run: |
          rc=0
          # a stale run-comment mention must not satisfy a term either
          signoff/check-pvt-grid.sh || rc=$?
          exit $rc
"""


def make_fixture(root, check_ci, yml=CI_CLEAN):
    write(root, "package.json", pkg(check_ci))
    write(root, "ci.yml", yml)
    return root


SELF_TEST_TERM = ("(cd scripts/ci && python3 -I -m unittest discover -s . "
                  "-p 'test_*.py' -v)")
CLEAN_CHAIN = " && ".join([
    SELF_TEST_TERM,
    "python3 scripts/ci/check_evidence_format.py",
    "signoff/check-pvt-grid.sh",
    "verification/run.sh",
    "echo 'check:ci OK -- hermetic checks only: this does NOT run the CI steps "
    "that need an EDA tool (verification/run.sh), so a green check:ci is not a "
    "prediction that CI will pass.'",
])


class Test(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def run_check(self, check_ci=CLEAN_CHAIN, yml=CI_CLEAN, exempt=None):
        make_fixture(self.root, check_ci, yml)
        return ccb.check(self.root / "package.json", self.root / "ci.yml",
                         exempt=exempt)

    def run_main(self, check_ci=CLEAN_CHAIN, yml=CI_CLEAN, extra=()):
        make_fixture(self.root, check_ci, yml)
        out = StringIO()
        with redirect_stdout(out):
            code = ccb.main(["--package", str(self.root / "package.json"),
                             "--workflow", str(self.root / "ci.yml"), *extra])
        return code, out.getvalue()

    # -- the clean binding ---------------------------------------------------

    def test_clean_chain_binds_every_term(self):
        problems, stats = self.run_check()
        self.assertEqual([m for m, _ in problems], [])
        self.assertEqual(stats["terms"], 5)
        self.assertEqual(stats["matched"], 4)
        self.assertEqual(stats["echo_skipped"], 1)
        self.assertEqual(stats["jobs"], 2)
        self.assertEqual(stats["steps"], 6)

    def test_clean_run_exit_0_and_ok_line(self):
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("OK:", out)
        self.assertIn("4 matched", out)
        self.assertIn("0 unbound", out)

    # -- the seeded-bad cases (the drift this checker exists for) ------------

    def test_seeded_missing_step_is_rejected(self):
        seeded = CLEAN_CHAIN + " && python3 scripts/ci/check_missing_step.py"
        problems, stats = self.run_check(check_ci=seeded)
        msgs = [m for m, _ in problems]
        self.assertEqual(len(msgs), 1)
        self.assertIn("check_missing_step.py", msgs[0])
        self.assertIn("no matching step", msgs[0])
        self.assertEqual(stats["terms"], 6)
        self.assertEqual(stats["matched"], 4)
        code, out = self.run_main(check_ci=seeded)
        self.assertEqual(code, 1)
        self.assertIn("FAIL:", out)
        self.assertIn("EXEMPT_TERMS", out)
        self.assertIn("add a ci.yml step", out)

    def test_run_comment_mention_does_not_satisfy_term(self):
        chain = " && ".join([
            SELF_TEST_TERM,
            "python3 scripts/ci/check_evidence_format.py",
            "verification/run.sh",
            "echo 'ok'",
        ])
        yml = CI_CLEAN.replace(
            "          # a stale run-comment mention must not satisfy a term "
            "either\n          signoff/check-pvt-grid.sh || rc=$?",
            "          # signoff/check-pvt-grid.sh || rc=$?")
        problems, _ = self.run_check(
            check_ci=chain + " && signoff/check-pvt-grid.sh", yml=yml)
        msgs = [m for m, _ in problems]
        self.assertEqual(len(msgs), 1)
        self.assertIn("check-pvt-grid.sh", msgs[0])

    def test_working_directory_binds_the_cd_term_only_with_the_run(self):
        problems, _ = self.run_check(yml=CI_CLEAN.replace(
            "-p 'test_*.py'", "-p 'other_*.py'"))
        msgs = [m for m, _ in problems]
        self.assertEqual(len(msgs), 1)
        self.assertIn("test_*.py", msgs[0])

    def test_keys_scattered_across_steps_do_not_match(self):
        problems, _ = self.run_check(
            check_ci=CLEAN_CHAIN + " && signoff/check-pvt-grid.sh "
            "python3 scripts/ci/check_evidence_format.py")
        msgs = [m for m, _ in problems]
        self.assertEqual(len(msgs), 1)
        self.assertIn("check-pvt-grid.sh", msgs[0])

    def test_term_without_path_token_is_rejected(self):
        problems, _ = self.run_check(check_ci=CLEAN_CHAIN + " && make all")
        msgs = [m for m, _ in problems]
        self.assertEqual(len(msgs), 1)
        self.assertIn("no path-like token", msgs[0])

    # -- echo terms and exemptions -------------------------------------------

    def test_echo_term_is_skipped_even_with_path_words(self):
        problems, stats = self.run_check(
            check_ci=CLEAN_CHAIN + " && echo 'see scripts/ci/never_run.py'")
        self.assertEqual([m for m, _ in problems], [])
        self.assertEqual(stats["echo_skipped"], 2)

    def test_exempt_term_passes_and_is_counted(self):
        seeded = CLEAN_CHAIN + " && python3 scripts/ci/check_missing_step.py"
        exempt = {"python3 scripts/ci/check_missing_step.py":
                  "CI runs it in a separate workflow by design"}
        problems, stats = self.run_check(check_ci=seeded, exempt=exempt)
        self.assertEqual([m for m, _ in problems], [])
        self.assertEqual(stats["exempt"], 1)
        self.assertEqual(stats["matched"], 4)

    def test_exempt_only_covers_its_exact_term(self):
        seeded = CLEAN_CHAIN + " && python3 scripts/ci/check_missing_step.py"
        exempt = {"python3 scripts/ci/check_other_step.py": "unrelated entry"}
        problems, _ = self.run_check(check_ci=seeded, exempt=exempt)
        self.assertEqual(len(problems), 1)

    def test_module_level_exempt_is_used_by_main(self):
        seeded = CLEAN_CHAIN + " && python3 scripts/ci/check_missing_step.py"
        old = dict(ccb.EXEMPT_TERMS)
        ccb.EXEMPT_TERMS.update(
            {"python3 scripts/ci/check_missing_step.py": "deliberate"})
        try:
            code, out = self.run_main(check_ci=seeded)
        finally:
            ccb.EXEMPT_TERMS.clear()
            ccb.EXEMPT_TERMS.update(old)
        self.assertEqual(code, 0)
        self.assertIn("1 exempt", out)

    # -- term parsing ---------------------------------------------------------

    def test_unbalanced_quote_term_is_reported_not_crash(self):
        problems, _ = self.run_check(check_ci=CLEAN_CHAIN + " && echo 'unclosed")
        msgs = [m for m, _ in problems]
        self.assertEqual(len(msgs), 1)
        self.assertIn("does not shell-tokenize", msgs[0])

    def test_stray_and_separator_is_reported(self):
        problems, _ = self.run_check(
            check_ci="scripts/a.sh && && scripts/b.sh")
        msgs = [m for m, _ in problems]
        self.assertEqual(len(msgs), 1)
        self.assertIn("empty term", msgs[0])

    def test_empty_script_is_reported(self):
        problems, _ = self.run_check(check_ci="   ")
        msgs = [m for m, _ in problems]
        self.assertEqual(len(msgs), 1)
        self.assertIn("missing or empty", msgs[0])

    # -- structural problems with the inputs ----------------------------------

    def test_unparseable_package_json_is_reported(self):
        write(self.root, "package.json", "{oops")
        write(self.root, "ci.yml", CI_CLEAN)
        problems, _ = ccb.check(self.root / "package.json",
                                self.root / "ci.yml")
        msgs = [m for m, _ in problems]
        self.assertEqual(len(msgs), 1)
        self.assertIn("package.json", msgs[0])

    def test_missing_check_ci_script_is_reported(self):
        problems, _ = self.run_check()
        write(self.root, "package.json", pkg({"other": "true"}))
        problems, _ = ccb.check(self.root / "package.json",
                                self.root / "ci.yml")
        msgs = [m for m, _ in problems]
        self.assertEqual(len(msgs), 1)
        self.assertIn("check:ci", msgs[0])

    def test_workflow_without_jobs_is_reported(self):
        problems, _ = self.run_check(yml="name: ci\n")
        msgs = [m for m, _ in problems]
        self.assertEqual(len(msgs), 1)
        self.assertIn("jobs:", msgs[0])

    def test_workflow_without_steps_is_reported(self):
        yml = ("jobs:\n"
               "  caller:\n"
               "    uses: ./.github/workflows/reusable.yml\n")
        problems, _ = self.run_check(yml=yml)
        msgs = [m for m, _ in problems]
        self.assertEqual(len(msgs), 1)
        self.assertIn("no steps found", msgs[0])

    def test_value_less_run_is_reported(self):
        yml = CI_CLEAN.replace(
            "        run: python3 scripts/ci/check_evidence_format.py",
            "        run:")
        problems, _ = self.run_check(yml=yml)
        msgs = [m for m, _ in problems]
        self.assertEqual(len(msgs), 1)
        self.assertIn("'run' has no value", msgs[0])

    def test_duplicate_run_in_one_step_is_reported(self):
        yml = CI_CLEAN.replace(
            "        run: python3 scripts/ci/check_evidence_format.py",
            "        run: true\n"
            "        run: python3 scripts/ci/check_evidence_format.py")
        problems, _ = self.run_check(yml=yml)
        msgs = [m for m, _ in problems]
        self.assertEqual(len(msgs), 1)
        self.assertIn("duplicate 'run'", msgs[0])

    def test_job_key_after_steps_is_tolerated(self):
        yml = CI_CLEAN.replace(
            "  harness:\n    runs-on: ubuntu-latest\n",
            "  harness:\n    runs-on: ubuntu-latest\n"
            "    env:\n"
            "      EXAMPLE: value\n")
        problems, stats = self.run_check(yml=yml)
        self.assertEqual([m for m, _ in problems], [])
        self.assertEqual(stats["jobs"], 2)


if __name__ == "__main__":
    unittest.main()
