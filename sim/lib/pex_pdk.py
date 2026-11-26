"""GF180D PEX model directory, checked against the repo's pinned GF180C simulator models."""
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = Path(os.environ.get("PDK_ROOT", Path.home() / ".ciel")).resolve() / "gf180mcuD/libs.tech/ngspice"


def pin_check():
    pin = json.loads((ROOT / "sim/pdk.json").read_text())
    ngspice = subprocess.check_output(["ngspice", "--version"], text=True)
    if not re.search(r"ngspice-" + re.escape(pin["ngspice_version"]) + r"\b", ngspice):
        raise ValueError(f"Use ngspice {pin['ngspice_version']} from sim/pdk.json")
    version_root = MODEL_DIR.parents[2]
    if (version_root / "gf180mcuD/SOURCES").read_text().strip() != "open_pdks " + pin["open_pdks_revision"]:
        raise ValueError("PDK_ROOT must name the open_pdks revision pinned in sim/pdk.json")
    canonical = version_root / pin["variant"] / "libs.tech/ngspice"
    for model_file in pin["fleet_checked_model_files"]:
        if (canonical / model_file).read_bytes() != (MODEL_DIR / model_file).read_bytes():
            raise ValueError(f"gf180mcuD differs from the pinned {pin['variant']} model: {model_file}")
