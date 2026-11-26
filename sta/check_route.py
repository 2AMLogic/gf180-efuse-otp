"""Bind all three controller STA requests to the routed DEF cited for item 5."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ("sta-100ns", "sta-10ns", "sta-negative-control-1ns")


def main():
    manifest = json.loads((ROOT / "signoff/block-manifest.json").read_text())
    reports = [ROOT / entry["file"] for entry in manifest["evidence"]["5.digital"]
               if Path(entry["file"]).parent == Path("sim/controller-sta")]
    if len(reports) != 1:
        raise SystemExit("Expected one cited controller timing report for digital item 5")
    source = json.loads(reports[0].read_text())
    if source["geometry_source"] != "routed" or source["provenance"]["input"]["role"] != "layout":
        raise SystemExit(f"{reports[0].name}: expected a routed layout input")
    route = ROOT / "layout/efuse_otp_ctrl.def"
    for name in REQUESTS:
        request = json.loads((ROOT / "sta" / f"{name}.json").read_text())
        if (ROOT / "sta" / request["def"]).resolve() != route:
            raise SystemExit(f"{name}: expected the retained controller DEF")
    actual = "sha256:" + hashlib.sha256(route.read_bytes()).hexdigest()
    if actual != source["provenance"]["input"]["content_hash"]:
        raise SystemExit(f"{route.name}: SHA-256 differs from {reports[0].name}")
    print(f"Three STA requests use {route.name} at {actual}")


if __name__ == "__main__":
    main()
