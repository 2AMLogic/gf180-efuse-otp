#!/usr/bin/env python3
"""Bind package.json's check:ci terms to the top-level README check:ci paragraph (stdlib only).

check_ci_yml_binding.py already binds each non-echo check:ci term to a ci.yml
step; the term -> top-level README.md enumeration binding stayed by hand, and
it has drifted once undetected (#248: check:ci chained
check_report_inputs.py while the README paragraph did not name it). This
checker closes that side the same way its sibling closes the CI side:

  - package.json's ``scripts["check:ci"]`` is split into terms on top-level
    ``&&`` and each term into shell words with the binding module's own
    ``split_terms``/``term_words`` -- the term grammar is defined once, in
    that module, not reimplemented here;
  - terms whose command word is ``echo`` are skipped: they print the summary
    line and assert nothing;
  - the README paragraph that opens with `` `npm run -s check:ci` `` (its
    first line, through the paragraph's next blank line) is located
    mechanically and only that paragraph is searched; if no paragraph opens
    that way the checker fails closed rather than passing;
  - a term is enumerated when that paragraph's text contains every
    path-like token of the term (a word containing ``/`` or ending in
    ``.py``/``.sh`` -- the same ``term_keys`` its sibling binds to ci.yml)
    literally.

On drift the checker names the offending term and the key(s) the paragraph
no longer contains. Exit 0 = every non-echo term enumerated, 1 = drift or
unparseable input. There is no exemption list: unlike the ci.yml binding,
where CI may deliberately skip a term, the README paragraph is meant to
enumerate every hermetic check -- a term that must stop being enumerated has
no reason to stay a check:ci term.

Run from the repo root as ``python3 scripts/ci/check_readme_enumeration.py``
(plain python3, like its sibling checkers: the local sibling import needs the
script directory on sys.path, which ``python3 -I`` strips on Python >= 3.11).
"""
import argparse
import json
import sys
from pathlib import Path

from check_ci_yml_binding import BindError, split_terms, term_keys, term_words

PACKAGE = Path("package.json")
README = Path("README.md")
PARAGRAPH_OPEN = "`npm run -s check:ci`"


class ReadmeParseError(Exception):
    """A structural problem with the README input, not term drift."""


def find_paragraph(readme_text):
    """The paragraph whose first line opens with PARAGRAPH_OPEN, verbatim."""
    for para in readme_text.split("\n\n"):
        if para.startswith(PARAGRAPH_OPEN):
            return para
    raise ReadmeParseError(
        "no paragraph opens with %s -- the check:ci enumeration cannot be "
        "located; keep that paragraph's first line starting with this literal"
        % PARAGRAPH_OPEN)


def check(pkg_path=PACKAGE, readme_path=README):
    """Return (problems, stats); problems are (message, fix_or_None) tuples."""
    stats = {"terms": 0, "matched": 0, "echo_skipped": 0}
    try:
        pkg = json.loads(Path(pkg_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return ([("%s: unreadable or unparseable (%s)" % (pkg_path, e), None)],
                stats)
    scripts = pkg.get("scripts") if isinstance(pkg, dict) else None
    script = scripts.get("check:ci") if isinstance(scripts, dict) else None
    if not isinstance(script, str) or not script.strip():
        return ([("%s: scripts['check:ci'] is missing or empty -- nothing to bind"
                  % pkg_path, None)], stats)
    try:
        readme_text = Path(readme_path).read_text(encoding="utf-8")
    except OSError as e:
        return ([("%s: unreadable (%s)" % (readme_path, e), None)], stats)
    try:
        paragraph = find_paragraph(readme_text)
    except ReadmeParseError as e:
        return ([("%s: %s" % (readme_path, e), None)], stats)
    try:
        terms = split_terms(script)
    except BindError as e:
        return ([("%s: %s" % (pkg_path, e), None)], stats)
    problems = []
    fix = ("amend the %s check:ci paragraph so the term's clause names the "
           "missing path(s) literally" % readme_path)
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
        missing = [k for k in term_keys(words) if k not in paragraph]
        if missing:
            problems.append((
                "check:ci term %r is not enumerated in the %s check:ci "
                "paragraph: the paragraph does not contain %s"
                % (term, readme_path, ", ".join(repr(k) for k in missing)),
                fix))
        else:
            stats["matched"] += 1
    return problems, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--package", default=str(PACKAGE))
    ap.add_argument("--readme", default=str(README))
    args = ap.parse_args(argv)
    problems, stats = check(args.package, args.readme)
    for msg, fix in problems:
        print("FAIL:", msg)
        if fix:
            print("  fix:", end=" ")
            print("\n       ".join(fix.splitlines()))
    if problems:
        print("FAIL: %d term(s) against %s: %d enumerated, %d echo-skipped, "
              "%d problem(s) above"
              % (stats["terms"], args.readme, stats["matched"],
                 stats["echo_skipped"], len(problems)))
        return 1
    print("OK: check:ci enumerated in %s: %d term(s): %d enumerated, "
          "%d echo-skipped; 0 unenumerated"
          % (args.readme, stats["terms"], stats["matched"],
             stats["echo_skipped"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
