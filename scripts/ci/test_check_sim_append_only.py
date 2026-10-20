import subprocess
import tempfile
import unittest
from pathlib import Path

import check_sim_append_only as cao


def git(root, *a):
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                   check=True, capture_output=True)


def make_repo():
    root = Path(tempfile.mkdtemp())
    git(root, "init", "-q", "-b", "main")
    rd = root / "sim" / "t" / "records"
    rd.mkdir(parents=True)
    (rd / "a.json").write_text("{}\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    git(root, "checkout", "-q", "-b", "pr")
    return root, rd


def finish(root):
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "change")
    return cao.main(["--base", "main", "--root", str(root)])


class Test(unittest.TestCase):
    def test_add_accepted(self):
        root, rd = make_repo()
        (rd / "b.json").write_text("{}\n")
        self.assertEqual(finish(root), 0)

    def test_modify_rejected(self):
        root, rd = make_repo()
        (rd / "a.json").write_text('{"x": 1}\n')
        self.assertNotEqual(finish(root), 0)

    def test_delete_rejected(self):
        root, rd = make_repo()
        (rd / "a.json").unlink()
        self.assertNotEqual(finish(root), 0)

    def test_rename_rejected(self):
        root, rd = make_repo()
        (rd / "a.json").rename(rd / "c.json")
        self.assertNotEqual(finish(root), 0)

    def test_non_record_edit_accepted(self):
        root, _ = make_repo()
        (root / "sim" / "README.md").write_text("edited\n")
        self.assertEqual(finish(root), 0)

    def test_zero_base_skipped(self):
        self.assertEqual(cao.main(["--base", "0" * 40]), 0)


if __name__ == "__main__":
    unittest.main()
