#!/usr/bin/env python3
"""Check attestation-envelope path pins, composite digests and manifest bindings (stdlib only).

Every tracked ``*.json`` whose top level carries an ``attestation`` object is an
envelope. For each envelope three pin shapes are verified:

  1. ``attestation.checks[]`` entries carrying both ``path`` and ``content_hash``
     (klt's ``check: "present"``). Entries with a hash but no path
     (``stream_readable``, which duplicates ``provenance.input.content_hash``)
     and entries with no hash (``command``, ``citation``, ``metric``, ``pin``,
     ``dbu_on_grid``, ``top_cell_non_empty``) are skipped, not reported.
  2. ``provenance.input.path`` + ``content_hash`` (single-file envelopes).
  3. ``provenance.input.paths[]`` members (multi-file envelopes), plus the
     composite ``provenance.input.content_hash``: sha256 over sha256sum-format
     ``"{hex}  {path}\\n"`` lines built from the freshly hashed members, in
     stored order.

``hash_algorithm: "sha256-raw-bytes"`` is assumed to be plain sha256 over the
file's bytes and the composite recipe above is assumed to be what klt computes;
both assumptions are pinned by ``test_check_attest_pins.py``, so a future klt
hash-kind or envelope-shape change breaks a named test instead of quietly
disagreeing with CI. This checker mirrors what ``klt signoff --check`` reports;
CI stays the authority and this is strictly the earlier, cheaper local signal.

Finally, every ``signoff/block-manifest.json`` ``evidence[]`` entry carrying a
``content_hash`` must equal the cited envelope's ``provenance.input.content_hash``
(entries without a hash are skipped).

On drift the checker names the offending path, its committed and fresh hash, and
the per-item "Re-attest item N" remediation from ``signoff/README.md`` — item 1
additionally requires the ``block-manifest.json`` ``content_hash`` update.

Run from the repository root (any directory lacking ``signoff/block-manifest.json``
is refused with a message). Exit 0 = clean, 1 = drift or structural problem.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

MANIFEST = Path("signoff") / "block-manifest.json"
SKIP_WALK = {".git", ".loom", "node_modules", "__pycache__"}
NO_HASH_KINDS = ("command", "citation", "metric", "pin", "dbu_on_grid",
                 "top_cell_non_empty")

_ATTEST = 'uvx --from "$(cat signoff/klt-pin.txt)" klt signoff'
_REGRADE = (f'{_ATTEST} --manifest signoff/block-manifest.json \\\n'
            '  --tiers-doc signoff/design-evidence-tiers.md --format json')

MANIFEST_FIX = (
    'set evidence["{key}"].content_hash in signoff/block-manifest.json to the cited\n'
    "envelope's provenance.input.content_hash, then regenerate the signoff record and\n"
    'cmp it against signoff/block-manifest.signoff.json (CI\'s "Re-grade signoff\n'
    'record" step):\n'
    f'    {_REGRADE}')

GENERIC_FIX = ('no per-item procedure is recorded for this envelope — see the\n'
               '"Re-attest item N" sections in signoff/README.md')

REMEDIATION = {
    "signoff/item1-digital.attest.json": (
        're-attest per signoff/README.md "Re-attest item 1 (digital)":\n'
        '    rtl/regen-gl.sh\n'
        f'    {_ATTEST} --attest 1 \\\n'
        '      --inventory signoff/item1-digital-inventory.json \\\n'
        '      -o signoff/item1-digital.attest.json\n'
        'then set evidence["1.digital"].content_hash in signoff/block-manifest.json to this\n'
        "envelope's provenance.input.content_hash (the composite over the input set) and\n"
        'regenerate the signoff record.'),
    "signoff/item1-analog.attest.json": (
        're-attest per signoff/README.md "Re-attest item 1 (analog)":\n'
        '    design/regen-netlist.sh\n'
        f'    {_ATTEST} --attest 1 \\\n'
        '      --inventory signoff/item1-analog-inventory.json \\\n'
        '      -o signoff/item1-analog.attest.json\n'
        'then set evidence["1.analog"].content_hash in signoff/block-manifest.json to this\n'
        "envelope's provenance.input.content_hash (the composite over the input set) and\n"
        'regenerate the signoff record.'),
    "signoff/attest/item8.envelope.json": (
        're-attest per signoff/README.md "Re-attest item 8 (characterization report)"\n'
        "(pass --format json; 0.9.0's text renderer crashes on citation checks):\n"
        f'    {_ATTEST} --attest 8 \\\n'
        '      --inventory signoff/attest/item8.json \\\n'
        '      -o signoff/attest/item8.envelope.json --format json\n'
        'then set evidence["8.analog"] and evidence["8.digital"].content_hash in\n'
        'signoff/block-manifest.json to the sha256 of attest/item8.json (this envelope\'s\n'
        'provenance.input.content_hash) and regenerate the signoff record.'),
    "signoff/attest/item9.envelope.json": (
        're-attest per signoff/README.md "Re-attest item 9 (testbenches shipped)"\n'
        '(--attest runs sim/cold-start.sh, which needs the PDK, ngspice and Icarus):\n'
        f'    {_ATTEST} --attest 9 \\\n'
        '      --inventory signoff/attest/item9.json \\\n'
        '      -o signoff/attest/item9.envelope.json\n'
        'then set evidence["9"].content_hash in signoff/block-manifest.json to the sha256\n'
        "of attest/item9.json (this envelope's provenance.input.content_hash) and\n"
        'regenerate the signoff record.'),
    "signoff/attest/item10.envelope.json": (
        're-attest per signoff/README.md "Re-attest item 10 (repo hygiene)":\n'
        f'    {_ATTEST} --attest 10 \\\n'
        '      --inventory signoff/attest/item10.json \\\n'
        '      -o signoff/attest/item10.envelope.json\n'
        'then set evidence["10"].content_hash in signoff/block-manifest.json to the sha256\n'
        "of attest/item10.json (this envelope's provenance.input.content_hash) and\n"
        'regenerate the signoff record.'),
    "signoff/item2-analog.attest.json": (
        're-attest per signoff/README.md "Re-attest item 2 (both layout streams)":\n'
        '    layout/pnr.sh        # digital stream (needs the PDK)\n'
        '    layout/regen-gds.sh  # analog stream (needs the PDK)\n'
        '    layout/attest.sh     # rewrites both item 2 envelopes\n'
        'then set evidence["2.digital"] and evidence["2.analog"].content_hash in\n'
        "signoff/block-manifest.json to each envelope's provenance.input.content_hash\n"
        "(the stream's own sha256) and regenerate the signoff record."),
    "layout/pnr.attest.json": (
        're-attest per signoff/README.md "Re-attest item 2 (both layout streams)":\n'
        '    layout/pnr.sh        # digital stream (needs the PDK)\n'
        '    layout/regen-gds.sh  # analog stream (needs the PDK)\n'
        '    layout/attest.sh     # rewrites both item 2 envelopes\n'
        'then set evidence["2.digital"] and evidence["2.analog"].content_hash in\n'
        "signoff/block-manifest.json to each envelope's provenance.input.content_hash\n"
        "(the stream's own sha256) and regenerate the signoff record."),
}


def sha256_raw(path):
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return f"sha256:{digest}"


def path_str(node):
    if isinstance(node, dict):
        node = node.get("path")
    return node if isinstance(node, str) else None


def tracked_json(root):
    proc = subprocess.run(["git", "ls-files", "--cached", "-z", "--", "*.json"],
                          cwd=root, capture_output=True)
    if proc.returncode != 0:
        return None
    return sorted(name.decode("utf-8", "surrogateescape")
                  for name in proc.stdout.split(b"\0") if name)


def walked_json(root):
    found = []
    for path in sorted(root.rglob("*.json")):
        if not SKIP_WALK.intersection(path.relative_to(root).parts):
            found.append(path.relative_to(root).as_posix())
    return found


def discover(root):
    tracked = tracked_json(root)
    return tracked if tracked is not None else walked_json(root)


def remediation_for(env):
    return REMEDIATION.get(env, GENERIC_FIX)


def hash_pin(env, where, rel, committed, root, fresh):
    full = root / rel
    if not full.is_file():
        return (f"{env}: {where}: pinned path is missing: {rel} "
                f"(committed {committed})", remediation_for(env))
    digest = sha256_raw(full)
    fresh[rel] = digest
    if digest != committed:
        return (f"{env}: {where}: {rel}: committed {committed} != fresh {digest}",
                remediation_for(env))
    return None


def check_envelope(env, data, root):
    problems = []
    pins = composites = skipped = 0
    att = data["attestation"]
    checks = att.get("checks", [])
    if not isinstance(checks, list):
        return [(f"{env}: attestation.checks must be a list", None)], 0, 0, 0
    fresh = {}
    for i, c in enumerate(checks):
        if not isinstance(c, dict):
            problems.append((f"{env}: attestation.checks[{i}] is not an object", None))
            continue
        if "content_hash" not in c or "path" not in c:
            skipped += 1
            continue
        where = f"attestation.checks[{i}]"
        rel = path_str(c["path"])
        if rel is None:
            problems.append((f"{env}: {where}.path is neither a string nor a path object",
                             None))
            continue
        pins += 1
        bad = hash_pin(env, where, rel, c["content_hash"], root, fresh)
        if bad:
            problems.append(bad)
    prov = data.get("provenance")
    inp = prov.get("input") if isinstance(prov, dict) else None
    if isinstance(inp, dict):
        if "path" in inp and "content_hash" in inp:
            rel = path_str(inp["path"])
            if rel is None:
                problems.append((f"{env}: provenance.input.path is malformed", None))
            else:
                pins += 1
                bad = hash_pin(env, "provenance.input", rel,
                               inp["content_hash"], root, fresh)
                if bad:
                    problems.append(bad)
        members = inp.get("paths")
        if members is not None:
            if not isinstance(members, list):
                problems.append((f"{env}: provenance.input.paths must be a list", None))
            else:
                p, n, c = _check_paths(env, inp, members, root, fresh)
                problems.extend(p)
                pins += n
                composites += c
    return problems, pins, composites, skipped


def _check_paths(env, inp, members, root, fresh):
    problems = []
    pins = composites = 0
    lines = []
    broken = False
    for i, m in enumerate(members):
        where = f"provenance.input.paths[{i}]"
        if not isinstance(m, dict) or "content_hash" not in m:
            problems.append((f"{env}: {where} is malformed", None))
            broken = True
            continue
        rel = path_str(m.get("path"))
        if rel is None:
            problems.append((f"{env}: {where}.path is malformed", None))
            broken = True
            continue
        pins += 1
        bad = hash_pin(env, where, rel, m["content_hash"], root, fresh)
        if bad:
            problems.append(bad)
            broken = True
        else:
            lines.append(f"{fresh[rel].split(':', 1)[1]}  {rel}\n")
    if "content_hash" in inp and not broken and lines:
        composite = "sha256:" + hashlib.sha256(
            "".join(lines).encode("utf-8")).hexdigest()
        if composite != inp["content_hash"]:
            problems.append((f"{env}: provenance.input.content_hash (composite): "
                             f"committed {inp['content_hash']} != fresh {composite}",
                             remediation_for(env)))
        else:
            composites += 1
    return problems, pins, composites


def check_manifest(root, envs):
    problems = []
    manifest_pins = 0
    try:
        man = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [(f"{MANIFEST}: unreadable or unparseable ({e})", None)], 0
    evidence = man.get("evidence") if isinstance(man, dict) else None
    if not isinstance(evidence, dict):
        return [(f"{MANIFEST}: no evidence object", None)], 0
    for key, entry in sorted(evidence.items()):
        if not isinstance(entry, dict) or "content_hash" not in entry:
            continue
        manifest_pins += 1
        cite = entry.get("file")
        if not isinstance(cite, str) or cite not in envs:
            problems.append(
                (f'{MANIFEST}: evidence["{key}"] cites {cite!r}, which is not a '
                 'tracked attestation envelope', None))
            continue
        bound = json.loads((root / cite).read_text(encoding="utf-8")).get(
            "provenance", {}).get("input", {}).get("content_hash")
        if bound is None:
            problems.append(
                (f'{MANIFEST}: evidence["{key}"] -> {cite}: envelope carries no '
                 'provenance.input.content_hash to bind against', None))
        elif bound != entry["content_hash"]:
            problems.append(
                (f'{MANIFEST}: evidence["{key}"] -> {cite}: committed '
                 f'{entry["content_hash"]} != envelope provenance.input.content_hash {bound}',
                 MANIFEST_FIX.format(key=key)))
    return problems, manifest_pins


def check(root):
    root = Path(root)
    if not (root / MANIFEST).is_file():
        return ([(f"this is not the repository root: {MANIFEST} is missing here — "
                  "run the checker from the repo root", None)],
                {"envelopes": 0, "pins": 0, "composites": 0, "manifest_pins": 0,
                 "skipped": 0})
    problems = []
    envelopes = set()
    pins = composites = skipped = 0
    for f in discover(root):
        try:
            data = json.loads((root / f).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            problems.append((f"{f}: unreadable or unparseable JSON ({e})", None))
            continue
        if not (isinstance(data, dict) and isinstance(data.get("attestation"), dict)):
            continue
        envelopes.add(f)
        p, n, c, s = check_envelope(f, data, root)
        problems.extend(p)
        pins += n
        composites += c
        skipped += s
    mp, manifest_pins = check_manifest(root, envelopes)
    problems.extend(mp)
    stats = {"envelopes": len(envelopes), "pins": pins, "composites": composites,
             "manifest_pins": manifest_pins, "skipped": skipped}
    return problems, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    problems, stats = check(args.root)
    for msg, fix in problems:
        print(f"FAIL: {msg}")
        if fix:
            print("  fix:", end=" ")
            print("\n       ".join(fix.splitlines()))
    if problems:
        print(f"FAIL: {stats['pins']} path pin(s), {stats['composites']} composite(s), "
              f"{stats['manifest_pins']} manifest pin(s) checked, "
              f"{len(problems)} problem(s) above")
        return 1
    print(f"OK: {stats['envelopes']} envelope(s): {stats['pins']} path pin(s), "
          f"{stats['composites']} composite(s), {stats['manifest_pins']} manifest "
          f"pin(s) all match; 0 drift ({stats['skipped']} unpinned check(s) skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
