import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import check_attest_pins as cap


def sha_of(root, rel):
    return "sha256:" + hashlib.sha256((root / rel).read_bytes()).hexdigest()


def write(root, rel, content):
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)


def write_bytes(root, rel, content):
    full = root / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(content)


def present(path, digest):
    return {"check": "present", "path": {"path": path, "scope": "repo"},
            "content_hash": digest}


def command_check(cmd):
    return {"check": "command", "role": "audit", "command": cmd}


def stream_readable(digest):
    return {"check": "stream_readable", "content_hash": digest}


def envelope(checks=(), prov_input=None):
    env = {"kind": "attestation-envelope", "schema_version": 1,
           "attestation": {"hash_algorithm": "sha256-raw-bytes",
                           "inventory_schema_version": 1,
                           "checks": list(checks)}}
    if prov_input is not None:
        env["provenance"] = {"input": prov_input}
    return env


def single_input(path, digest):
    return {"path": {"path": path, "scope": "repo"}, "content_hash": digest}


def make_root():
    root = Path(tempfile.mkdtemp())
    write(root, "signoff/block-manifest.json",
          json.dumps({"kind": "block-manifest", "evidence": {}}))
    return root


class Test(unittest.TestCase):
    def run_check(self, root):
        return cap.check(root)

    def run_main(self, root):
        out = StringIO()
        with redirect_stdout(out):
            code = cap.main(["--root", str(root)])
        return code, out.getvalue()

    def put_envelope(self, root, rel, env):
        write(root, rel, json.dumps(env, indent=2) + "\n")

    # -- the three pin shapes ------------------------------------------------

    def test_checks_entry_shape_pinned(self):
        root = make_root()
        write_bytes(root, "README.md", b"hello\n")
        write(root, "signoff/attest/x.json", json.dumps({"item": "x"}))
        self.put_envelope(root, "signoff/attest/x.envelope.json", envelope(
            checks=[present("README.md", sha_of(root, "README.md"))],
            prov_input=single_input("signoff/attest/x.json",
                                    sha_of(root, "signoff/attest/x.json"))))
        problems, stats = self.run_check(root)
        self.assertEqual(problems, [])
        self.assertEqual(stats["pins"], 2)

    def test_single_file_input_shape_pinned(self):
        root = make_root()
        write_bytes(root, "layout/ea.gds", b"\x00\x01gds")
        self.put_envelope(root, "layout/e.attest.json", envelope(
            prov_input=single_input("layout/ea.gds", sha_of(root, "layout/ea.gds"))))
        problems, stats = self.run_check(root)
        self.assertEqual(problems, [])
        self.assertEqual(stats["pins"], 1)

    def test_multi_path_shape_and_composite_pinned(self):
        root = make_root()
        files = ["rtl/a.v", "rtl/b.gl.v"]
        for f in files:
            write_bytes(root, f, f"module {f}\n".encode())
        members = [{"path": {"path": f, "scope": "repo"},
                    "content_hash": sha_of(root, f)} for f in files]
        lines = "".join(f"{m['content_hash'].split(':', 1)[1]}  {f}\n"
                        for m, f in zip(members, files))
        composite = "sha256:" + hashlib.sha256(lines.encode()).hexdigest()
        self.put_envelope(root, "signoff/x.attest.json", envelope(
            prov_input={"paths": members, "content_hash": composite}))
        problems, stats = self.run_check(root)
        self.assertEqual(problems, [])
        self.assertEqual(stats["pins"], 2)
        self.assertEqual(stats["composites"], 1)

    # -- skipped kinds -------------------------------------------------------

    def test_command_entries_skipped_not_failed(self):
        root = make_root()
        self.put_envelope(root, "signoff/attest/x.envelope.json", envelope(
            checks=[command_check("some --audit --command"),
                    {"check": "citation", "citation": "spec/x"},
                    {"check": "metric", "metric": "m"},
                    {"check": "pin", "pin": "p"},
                    {"check": "dbu_on_grid"},
                    {"check": "top_cell_non_empty"}],
            prov_input=None))
        problems, stats = self.run_check(root)
        self.assertEqual(problems, [])
        self.assertEqual(stats["pins"], 0)
        self.assertEqual(stats["skipped"], 6)

    def test_stream_readable_hash_without_path_skipped(self):
        root = make_root()
        write_bytes(root, "layout/ea.gds", b"gds")
        self.put_envelope(root, "layout/e.attest.json", envelope(
            checks=[stream_readable(sha_of(root, "layout/ea.gds"))],
            prov_input=single_input("layout/ea.gds", sha_of(root, "layout/ea.gds"))))
        problems, stats = self.run_check(root)
        self.assertEqual(problems, [])
        self.assertEqual(stats["pins"], 1)
        self.assertEqual(stats["skipped"], 1)

    # -- hash_algorithm guard ------------------------------------------------

    def _env_with_algorithm(self, root, **kw):
        write_bytes(root, "README.md", b"x\n")
        env = envelope(checks=[present("README.md", sha_of(root, "README.md"))])
        if "algo" in kw:
            env["attestation"]["hash_algorithm"] = kw["algo"]
        else:
            del env["attestation"]["hash_algorithm"]
        self.put_envelope(root, "signoff/attest/x.envelope.json", env)

    def test_unsupported_hash_algorithm_is_named_not_reported_as_drift(self):
        root = make_root()
        write_bytes(root, "README.md", b"x\n")
        # a stale pin: under the old behaviour this would be reported as drift
        env = envelope(checks=[present("README.md", "sha256:" + "0" * 64)])
        env["attestation"]["hash_algorithm"] = "sha256-truncated-128"
        self.put_envelope(root, "signoff/attest/x.envelope.json", env)
        problems, stats = self.run_check(root)
        self.assertEqual(len(problems), 1)
        msg, fix = problems[0]
        self.assertIn("sha256-truncated-128", msg)
        self.assertIn(cap.HASH_ALGORITHM, msg)
        self.assertNotIn("committed", msg)
        self.assertIsNone(fix)
        self.assertEqual(stats["pins"], 0)

    def test_non_string_or_null_hash_algorithm_is_refused_not_a_crash(self):
        for bad in (None, 7, ["sha256-raw-bytes"]):
            root = make_root()
            self._env_with_algorithm(root, algo=bad)
            problems, stats = self.run_check(root)
            self.assertEqual(len(problems), 1, bad)
            self.assertEqual(stats["pins"], 0)

    def test_absent_hash_algorithm_checks_pins_as_before(self):
        root = make_root()
        self._env_with_algorithm(root)
        problems, stats = self.run_check(root)
        self.assertEqual(problems, [])
        self.assertEqual(stats["pins"], 1)

    def test_declared_supported_hash_algorithm_checks_pins(self):
        root = make_root()
        self._env_with_algorithm(root, algo=cap.HASH_ALGORITHM)
        problems, stats = self.run_check(root)
        self.assertEqual(problems, [])
        self.assertEqual(stats["pins"], 1)

    # -- the two klt assumptions, pinned by name -----------------------------

    def test_assumption_sha256_raw_bytes_is_plain_file_sha256(self):
        root = make_root()
        write_bytes(root, "README.md", b"assumption\n")
        self.put_envelope(root, "signoff/attest/x.envelope.json", envelope(
            checks=[present("README.md",
                            "sha256:" + hashlib.sha256(b"assumption\n").hexdigest())]))
        problems, _ = self.run_check(root)
        self.assertEqual(problems, [])

    def test_assumption_composite_recipe_is_sha256sum_lines(self):
        root = make_root()
        files = ["a.src", "b.src"]
        for f in files:
            write_bytes(root, f, f"{f}\n".encode())
        members = [{"path": {"path": f, "scope": "repo"},
                    "content_hash": sha_of(root, f)} for f in files]
        expected = "sha256:" + hashlib.sha256(
            "".join(f"{sha_of(root, f).split(':', 1)[1]}  {f}\n"
                    for f in files).encode()).hexdigest()
        self.put_envelope(root, "signoff/x.attest.json", envelope(
            prov_input={"paths": members, "content_hash": expected}))
        problems, stats = self.run_check(root)
        self.assertEqual([m for m, _ in problems], [])
        self.assertEqual(stats["composites"], 1)

    def test_assumption_composite_recipe_rejects_wrong_digest(self):
        root = make_root()
        write_bytes(root, "a.src", b"a\n")
        members = [{"path": {"path": "a.src", "scope": "repo"},
                    "content_hash": sha_of(root, "a.src")}]
        self.put_envelope(root, "signoff/x.attest.json", envelope(
            prov_input={"paths": members, "content_hash": "sha256:" + "1" * 64}))
        problems, _ = self.run_check(root)
        msgs = [m for m, _ in problems]
        self.assertTrue(any("composite" in m for m in msgs), msgs)

    # -- drift reporting -----------------------------------------------------

    def test_drifted_pin_names_path_committed_and_fresh(self):
        root = make_root()
        write_bytes(root, "README.md", b"new content\n")
        stale = "sha256:" + "0" * 64
        self.put_envelope(root, "signoff/attest/x.envelope.json", envelope(
            checks=[present("README.md", stale)]))
        problems, _ = self.run_check(root)
        msgs = [m for m, _ in problems]
        self.assertTrue(any("README.md" in m and stale in m
                            and sha_of(root, "README.md") in m for m in msgs), msgs)

    def test_drifted_pin_prints_per_item_remediation(self):
        root = make_root()
        write_bytes(root, "README.md", b"edited\n")
        self.put_envelope(root, "signoff/attest/item10.envelope.json", envelope(
            checks=[present("README.md", "sha256:" + "0" * 64)]))
        code, out = self.run_main(root)
        self.assertEqual(code, 1)
        self.assertIn("README.md", out)
        self.assertIn("Re-attest item 10", out)
        self.assertIn("--attest 10", out)
        self.assertIn('signoff/klt-pin.txt', out)

    def test_item1_remediation_names_two_step_manifest_update(self):
        root = make_root()
        write_bytes(root, "rtl/efuse_otp_ctrl.v", b"always @(posedge clk);\n")
        self.put_envelope(root, "signoff/item1-digital.attest.json", envelope(
            checks=[present("rtl/efuse_otp_ctrl.v", "sha256:" + "0" * 64)]))
        _, out = self.run_main(root)
        self.assertIn("Re-attest item 1", out)
        self.assertIn("block-manifest.json", out)
        self.assertIn("1.digital", out)
        self.assertIn("regen-gl", out)

    def test_unknown_envelope_gets_generic_pointer(self):
        root = make_root()
        write_bytes(root, "some/file.src", b"x\n")
        self.put_envelope(root, "signoff/future.envelope.json", envelope(
            checks=[present("some/file.src", "sha256:" + "0" * 64)]))
        _, out = self.run_main(root)
        self.assertIn("signoff/README.md", out)
        self.assertNotIn("--attest", out)

    def test_missing_pinned_file_reports_missing_not_crash(self):
        root = make_root()
        self.put_envelope(root, "signoff/attest/x.envelope.json", envelope(
            checks=[present("gone/missing.md", "sha256:" + "0" * 64)]))
        problems, _ = self.run_check(root)
        msgs = [m for m, _ in problems]
        self.assertTrue(any("missing" in m and "gone/missing.md" in m for m in msgs), msgs)

    # -- envelope hygiene ----------------------------------------------------

    def test_envelope_with_no_pins_passes(self):
        root = make_root()
        self.put_envelope(root, "signoff/attest/empty.envelope.json", envelope(
            checks=[command_check("noop")]))
        problems, stats = self.run_check(root)
        self.assertEqual(problems, [])
        self.assertEqual(stats["pins"], 0)

    def test_unparseable_tracked_json_is_a_defect_not_a_crash(self):
        root = make_root()
        write(root, "signoff/attest/broken.json", "{not json")
        problems, _ = self.run_check(root)
        msgs = [m for m, _ in problems]
        self.assertTrue(any("broken.json" in m for m in msgs), msgs)

    def test_non_envelope_json_ignored(self):
        root = make_root()
        write(root, "plain.json", json.dumps({"schema_version": 3, "rows": []}))
        problems, stats = self.run_check(root)
        self.assertEqual(problems, [])
        self.assertEqual(stats["envelopes"], 0)

    # -- manifest layer ------------------------------------------------------

    def test_manifest_binding_matches_envelope_composite(self):
        root = make_root()
        write_bytes(root, "a.src", b"a\n")
        members = [{"path": {"path": "a.src", "scope": "repo"},
                    "content_hash": sha_of(root, "a.src")}]
        lines = f"{sha_of(root, 'a.src').split(':', 1)[1]}  a.src\n"
        composite = "sha256:" + hashlib.sha256(lines.encode()).hexdigest()
        self.put_envelope(root, "signoff/x.attest.json", envelope(
            prov_input={"paths": members, "content_hash": composite}))
        write(root, "signoff/block-manifest.json", json.dumps({
            "kind": "block-manifest",
            "evidence": {"1.digital": {"file": "signoff/x.attest.json",
                                       "content_hash": composite}}}))
        problems, stats = self.run_check(root)
        self.assertEqual(problems, [])
        self.assertEqual(stats["manifest_pins"], 1)

    def test_manifest_stale_binding_reported_with_fix(self):
        root = make_root()
        write_bytes(root, "a.src", b"a\n")
        self.put_envelope(root, "signoff/x.attest.json", envelope(
            prov_input=single_input("a.src", sha_of(root, "a.src"))))
        write(root, "signoff/block-manifest.json", json.dumps({
            "kind": "block-manifest",
            "evidence": {"10": {"file": "signoff/x.attest.json",
                                "content_hash": "sha256:" + "2" * 64}}}))
        problems, stats = self.run_check(root)
        self.assertEqual(stats["manifest_pins"], 1)
        msgs = [m for m, _ in problems]
        self.assertTrue(any('evidence["10"]' in m for m in msgs), msgs)
        _, out = self.run_main(root)
        self.assertIn("block-manifest.json", out)
        self.assertIn("design-evidence-tiers.md", out)

    def test_manifest_entries_without_hash_skipped(self):
        root = make_root()
        write(root, "signoff/block-manifest.json", json.dumps({
            "kind": "block-manifest",
            "evidence": {
                "5.analog": [{"file": "sim/x/records/r.json"}],
                "6.digital": {"file": None},
            }}))
        problems, stats = self.run_check(root)
        self.assertEqual(problems, [])
        self.assertEqual(stats["manifest_pins"], 0)

    def test_manifest_citing_file_without_provenance_reported(self):
        root = make_root()
        write(root, "signoff/block-manifest.json", json.dumps({
            "kind": "block-manifest",
            "evidence": {"9": {"file": "signoff/attest/gone.envelope.json",
                               "content_hash": "sha256:" + "3" * 64}}}))
        problems, _ = self.run_check(root)
        msgs = [m for m, _ in problems]
        self.assertTrue(any("gone.envelope.json" in m and "provenance" in m
                            for m in msgs), msgs)

    def test_manifest_binds_provenance_bearing_non_envelope(self):
        root = make_root()
        write(root, "layout/report.json", json.dumps({
            "schema_version": 2,
            "provenance": {"input": {"content_hash": "sha256:" + "4" * 64}},
        }))
        write(root, "signoff/block-manifest.json", json.dumps({
            "kind": "block-manifest",
            "evidence": {"4.digital": {"file": "layout/report.json",
                                       "content_hash": "sha256:" + "4" * 64}}}))
        problems, stats = self.run_check(root)
        self.assertEqual(problems, [])
        self.assertEqual(stats["manifest_pins"], 1)

    def test_manifest_stale_non_envelope_binding_reported(self):
        root = make_root()
        write(root, "layout/report.json", json.dumps({
            "schema_version": 2,
            "provenance": {"input": {"content_hash": "sha256:" + "4" * 64}},
        }))
        write(root, "signoff/block-manifest.json", json.dumps({
            "kind": "block-manifest",
            "evidence": {"4.digital": {"file": "layout/report.json",
                                       "content_hash": "sha256:" + "5" * 64}}}))
        problems, stats = self.run_check(root)
        self.assertEqual(stats["manifest_pins"], 1)
        msgs = [m for m, _ in problems]
        self.assertTrue(any('evidence["4.digital"]' in m for m in msgs), msgs)

    # -- repo-root requirement and discovery ---------------------------------

    def test_run_outside_repo_root_says_so(self):
        root = Path(tempfile.mkdtemp())
        code, out = self.run_main(root)
        self.assertEqual(code, 1)
        self.assertIn("repo root", out)

    def test_tracked_only_discovery_ignores_untracked(self):
        if shutil.which("git") is None:
            self.skipTest("git not available")
        root = make_root()
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        write_bytes(root, "tracked.md", b"tracked\n")
        self.put_envelope(root, "signoff/attest/x.envelope.json", envelope(
            checks=[present("tracked.md", sha_of(root, "tracked.md"))]))
        write_bytes(root, "untracked.md", b"untracked\n")
        self.put_envelope(root, "signoff/attest/y.envelope.json", envelope(
            checks=[present("untracked.md", "sha256:" + "0" * 64)]))
        subprocess.run(["git", "add", "tracked.md",
                        "signoff/block-manifest.json",
                        "signoff/attest/x.envelope.json"],
                       cwd=root, check=True)
        problems, stats = self.run_check(root)
        self.assertEqual([m for m, _ in problems], [])
        self.assertEqual(stats["envelopes"], 1)

    # -- clean run output ----------------------------------------------------

    def test_clean_run_exit_0_and_ok_line(self):
        root = make_root()
        write_bytes(root, "README.md", b"ok\n")
        self.put_envelope(root, "signoff/attest/x.envelope.json", envelope(
            checks=[present("README.md", sha_of(root, "README.md"))]))
        code, out = self.run_main(root)
        self.assertEqual(code, 0)
        self.assertIn("OK:", out)
        self.assertIn("1 path pin", out)


if __name__ == "__main__":
    unittest.main()
