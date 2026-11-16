#!/usr/bin/env python3
"""Bind package.json's check:ci terms to .github/workflows/ci.yml step coverage (stdlib only).

check:ci chains the repo's hermetic checks with ``&&`` and the same commands
are re-run as steps of the ci.yml jobs; both sides are otherwise kept in sync
by hand, which has drifted repeatedly (#217, #230, #231 -- the last time
between a PR's own CI run and its merge, which no amount of per-PR care
catches). This checker parses both sides mechanically:

  - package.json's ``scripts["check:ci"]`` is split into terms on top-level
    ``&&`` (paren- and quote-aware, so the ``(cd scripts/ci && ...)``
    self-test subshell stays one term; shell backslash escapes and ``||`` are
    not used by the script and are not supported);
  - terms whose command word is ``echo`` are skipped: they print the summary
    line and assert nothing;
  - ci.yml is walked for job steps, and a step's invocation text is its
    ``run:`` value (block scalars dedented, full-line ``#`` comment lines
    dropped so a stale mention inside a run comment cannot satisfy a term)
    plus its ``working-directory:``;
  - a term is covered when some single step's invocation text contains every
    path-like token of the term -- words containing ``/`` or ending in
    ``.py``/``.sh``. Interpreter and flag words (``python3``, ``-I``,
    ``unittest``) are not required to appear verbatim. Coverage in any job
    counts: today every term is a ``harness`` step, but the binding that
    matters is "CI runs it somewhere", not "CI runs it in one particular job".

The matcher is a coverage signal, not an execution-equivalence proof: a step
whose command text merely contains the path satisfies the term. Which checks
CI runs is out of scope by design -- steps with no check:ci term (the klt
attestation steps, Sim records append-only, this checker's own step) are not
its concern, and check:ci stays hermetic-only.

A term CI deliberately skips is exempted by adding its normalized form (the
shlex-word join of the term after outer-paren stripping) to ``EXEMPT_TERMS``
below, with the reason. The list is empty today: every check:ci term is a CI
step, and each entry must carry a reason -- an undocumented exemption defeats
the binding this checker exists to enforce.

On drift the checker names the offending term, the tokens no step covers, and
both remediations (add a step, or document the exemption). Exit 0 = bound,
1 = drift or unparseable input.
"""
import argparse
import json
import shlex
import sys
from pathlib import Path

PACKAGE = Path("package.json")
WORKFLOW = Path(".github/workflows/ci.yml")

# Normalized check:ci term -> why CI deliberately does not run it. Empty
# today; see the module docstring for the entry format.
EXEMPT_TERMS = {}


class BindError(Exception):
    """A structural problem with the inputs, not term drift."""


class WorkflowParseError(BindError):
    pass


def split_terms(script):
    """Split a package.json script on top-level && (paren- and quote-aware)."""
    terms, buf, depth, quote, empty = [], [], 0, None, 0
    i, n = 0, len(script)
    while i < n:
        ch = script[i]
        if quote is not None:
            buf.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and script.startswith("&&", i):
            term = "".join(buf).strip()
            if term:
                terms.append(term)
            else:
                empty += 1
            buf = []
            i += 2
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        terms.append(tail)
    if not terms:
        raise BindError("check:ci script is empty after splitting on '&&'")
    if empty:
        raise BindError("check:ci script has %d empty term(s) -- a stray '&&'?" % empty)
    return terms


def term_words(term):
    stripped = term.strip()
    if stripped.startswith("(") and stripped.endswith(")"):
        stripped = stripped[1:-1].strip()
    try:
        words = shlex.split(stripped, posix=True)
    except ValueError as e:
        raise BindError("check:ci term %r does not shell-tokenize: %s" % (term, e))
    if not words:
        raise BindError("check:ci term %r has no words" % term)
    return words


def term_keys(words):
    return [w for w in words if "/" in w or w.endswith((".py", ".sh"))]


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _plain_value(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _strip_run_comments(run_text):
    return "\n".join(l for l in run_text.split("\n")
                     if not l.lstrip().startswith("#"))


def _read_block_scalar(lines, key_i, key_indent):
    """Dedented content of the block scalar starting after lines[key_i]."""
    out = []
    content_indent = None
    j = key_i + 1
    while j < len(lines):
        line = lines[j]
        if line.strip() == "":
            out.append("")
            j += 1
            continue
        ind = _indent(line)
        if content_indent is None:
            if ind <= key_indent:
                break
            content_indent = ind
        if ind < content_indent:
            break
        out.append(line[content_indent:])
        j += 1
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out), j


def parse_workflow_steps(text):
    """Return [{"job", "name", "run", "working_directory"}] for every job step.

    Walks the indentation shape GitHub Actions workflow files use here --
    top-level ``jobs:``, job keys at indent 2, ``steps:`` at indent 4, step
    items at indent 6, step keys at indent 8, block-scalar content deeper --
    and raises WorkflowParseError naming the offending line when the file
    stops matching that shape. No YAML dependency (stdlib-only like its
    siblings): a future ci.yml edit that needs richer YAML fails the parse
    loudly instead of silently passing the binding.
    """
    raw = text.split("\n")
    lines, starts = [], set()
    for idx, line in enumerate(raw):
        if line.startswith(" " * 6) and line[6:8] == "- ":
            lines.append(" " * 8 + line[8:])
            starts.add(idx)
        else:
            lines.append(line)

    def sig(i):
        while i is not None and i < len(lines):
            s = lines[i].strip()
            if s and not s.startswith("#"):
                return i
            i += 1
        return None

    jobs_i = next((i for i, l in enumerate(lines) if l.rstrip() == "jobs:"), None)
    if jobs_i is None:
        raise WorkflowParseError("no top-level 'jobs:' key found")

    def skip_step_subblock(j):
        """First significant line at indent <= 8 at/after j (None at EOF)."""
        while j is not None:
            nxt = sig(j)
            if nxt is None or _indent(lines[nxt]) <= 8:
                return nxt
            j = nxt + 1
        return None

    steps = []
    i = sig(jobs_i + 1)
    while i is not None:
        i = sig(i)
        if i is None:
            break
        line = lines[i]
        ind = _indent(line)
        stripped = line.strip()
        if ind == 0:
            break
        if ind == 2 and stripped.endswith(":") and ":" not in stripped[:-1]:
            i = _parse_job(lines, starts, sig, skip_step_subblock, i,
                           stripped[:-1], steps)
            continue
        if ind >= 4:
            # a job-level key of the previous job trailing after its steps
            # (e.g. job-level env:), or one of its children: walk on, the next
            # indent-2 job key is handled properly when reached.
            i = sig(i + 1)
            continue
        raise WorkflowParseError(
            "line %d: expected a job key at indent 2 under jobs:, got %r"
            % (i + 1, stripped))
    if not steps:
        raise WorkflowParseError("no steps found under any job")
    return steps


def _parse_job(lines, starts, sig, skip_step_subblock, job_i, job, steps):
    i = sig(job_i + 1)
    while i is not None:
        i = sig(i)
        if i is None:
            return None
        stripped = lines[i].strip()
        ind = _indent(lines[i])
        if ind <= 2:
            return i
        if ind == 4 and stripped == "steps:":
            return _parse_steps(lines, starts, sig, skip_step_subblock, i,
                                job, steps)
        i = sig(i + 1)
    return None


def _parse_steps(lines, starts, sig, skip_step_subblock, steps_i, job, steps):
    cur = None
    j = sig(steps_i + 1)
    while j is not None:
        j = sig(j)
        if j is None:
            return None
        line = lines[j]
        ind = _indent(line)
        if ind < 8:
            return j  # end of the steps list
        if ind != 8:
            raise WorkflowParseError(
                "line %d: unexpected indent %d inside a step: %r"
                % (j + 1, ind, line.strip()))
        stripped = line.strip()
        key, sep, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if j in starts:
            cur = {"job": job, "name": None, "run": None,
                   "working_directory": None}
            steps.append(cur)
        if cur is None:
            raise WorkflowParseError(
                "line %d: expected a '- ' step item at indent 6 under steps:, "
                "got %r" % (j + 1, stripped))
        if not sep:
            raise WorkflowParseError(
                "line %d: expected 'key: value' in a step, got %r"
                % (j + 1, stripped))
        if key in ("name", "run", "working-directory"):
            field = {"name": "name", "run": "run",
                     "working-directory": "working_directory"}[key]
            if cur[field] is not None:
                raise WorkflowParseError(
                    "line %d: duplicate %r in one step" % (j + 1, key))
            if not value:
                raise WorkflowParseError(
                    "line %d: %r has no value" % (j + 1, key))
            if key == "run" and value[0] in "|>":
                content, after = _read_block_scalar(lines, j, 8)
                cur[field] = _strip_run_comments(content)
                j = after
                continue
            cur[field] = _strip_run_comments(_plain_value(value))
        elif not value:
            j = skip_step_subblock(j + 1)
            if j is None:
                return None
            continue
        j = sig(j + 1)
    return None


def check(pkg_path=PACKAGE, yml_path=WORKFLOW, exempt=None):
    """Return (problems, stats); problems are (message, fix_or_None) tuples."""
    exempt = EXEMPT_TERMS if exempt is None else exempt
    stats = {"terms": 0, "matched": 0, "echo_skipped": 0, "exempt": 0,
             "jobs": 0, "steps": 0}
    try:
        pkg = json.loads(Path(pkg_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return ([("%s: unreadable or unparseable (%s)" % (pkg_path, e), None)], stats)
    scripts = pkg.get("scripts") if isinstance(pkg, dict) else None
    script = scripts.get("check:ci") if isinstance(scripts, dict) else None
    if not isinstance(script, str) or not script.strip():
        return ([("%s: scripts['check:ci'] is missing or empty -- nothing to bind"
                  % pkg_path, None)], stats)
    try:
        text = Path(yml_path).read_text(encoding="utf-8")
    except OSError as e:
        return ([("%s: unreadable (%s)" % (yml_path, e), None)], stats)
    try:
        steps = parse_workflow_steps(text)
    except WorkflowParseError as e:
        return ([("%s: %s" % (yml_path, e), None)], stats)
    stats["steps"] = len(steps)
    stats["jobs"] = len({s["job"] for s in steps})
    step_texts = [(s["run"] or "") + "\n" + (s["working_directory"] or "")
                  for s in steps]
    try:
        terms = split_terms(script)
    except BindError as e:
        return ([("%s: %s" % (pkg_path, e), None)], stats)
    problems = []
    fix = ("add a ci.yml step that runs the term (see the harness job's other "
           "checker steps), or -- only if CI deliberately skips the term -- add "
           "its normalized form to EXEMPT_TERMS in "
           "scripts/ci/check_ci_yml_binding.py with a reason")
    for term in terms:
        stats["terms"] += 1
        try:
            words = term_words(term)
        except BindError as e:
            problems.append((str(e), None))
            continue
        if words[0] == "echo":
            stats["echo_skipped"] += 1
            continue
        normalized = " ".join(words)
        if normalized in exempt:
            stats["exempt"] += 1
            continue
        keys = term_keys(words)
        if not keys:
            problems.append((
                "check:ci term %r has no path-like token (a word containing '/' "
                "or ending in .py/.sh) to bind a ci.yml step with -- write the "
                "term as an explicit script path, or exempt it in EXEMPT_TERMS "
                "with a reason" % term, None))
            continue
        if not any(all(k in text_ for k in keys) for text_ in step_texts):
            problems.append((
                "check:ci term %r has no matching step in %s: no single step's "
                "run/working-directory contains all of %s"
                % (term, yml_path, ", ".join(repr(k) for k in keys)), fix))
        else:
            stats["matched"] += 1
    return problems, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--package", default=str(PACKAGE))
    ap.add_argument("--workflow", default=str(WORKFLOW))
    args = ap.parse_args(argv)
    problems, stats = check(args.package, args.workflow)
    for msg, fix in problems:
        print("FAIL:", msg)
        if fix:
            print("  fix:", end=" ")
            print("\n       ".join(fix.splitlines()))
    if problems:
        print("FAIL: %d term(s) across %d job(s)/%d step(s): %d matched, "
              "%d echo-skipped, %d exempt, %d problem(s) above"
              % (stats["terms"], stats["jobs"], stats["steps"],
                 stats["matched"], stats["echo_skipped"], stats["exempt"],
                 len(problems)))
        return 1
    print("OK: check:ci bound to %s: %d term(s) across %d job(s)/%d step(s): "
          "%d matched, %d echo-skipped, %d exempt; 0 unbound"
          % (args.workflow, stats["terms"], stats["jobs"], stats["steps"],
             stats["matched"], stats["echo_skipped"], stats["exempt"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
