"""Run the selected-device body ties and narrow-select control on the refined high-R deck."""
import json
from pathlib import Path
import re
import subprocess
import sys


def replace_once(deck, original, replacement):
    if deck.count(original) != 1:
        raise ValueError(f"Expected one instance of {original!r}")
    return deck.replace(original, replacement)


def measure(directory, name, deck):
    path = directory / f"{name}.cir"
    path.write_text(deck)
    result = subprocess.run(["ngspice", "-b", str(path)], capture_output=True, text=True)
    path.with_suffix(".log").write_text(result.stdout + result.stderr)
    result.check_returncode()
    match = re.search(r"^i_fuse\s*=\s*(\S+)", result.stdout, re.M)
    if not match:
        raise ValueError(f"No i_fuse measurement in {path.with_suffix('.log')}")
    return round(float(match[1]) * 1000, 7)


def main():
    path = Path(sys.argv[1])
    source_tied = path.read_text()
    pmos_supply = source_tied
    for i in range(3):
        prefix = f"XMdrv{i} mdd{i} pg mds{i} "
        pmos_supply = replace_once(pmos_supply, prefix + f"mds{i} ", prefix + "vprog ")

    nmos = "XXsel sd wl vss "
    cases = {
        "source_tied_pmos_and_nmos": source_tied,
        "vprog_pmos_source_tied_nmos": pmos_supply,
        "source_tied_pmos_ground_nmos": replace_once(source_tied, nmos + "vss ", nmos + "0 "),
        "vprog_pmos_ground_nmos": replace_once(pmos_supply, nmos + "vss ", nmos + "0 "),
        "undersized_4um_select_high_ma": replace_once(
            source_tied, nmos + "vss nfet_06v0 L=0.7u W=60u", nmos + "vss nfet_06v0 L=0.7u W=4u"
        ),
    }
    currents = {name: measure(path.parent, name, deck) for name, deck in cases.items()}
    output = json.dumps(currents, indent=2)
    (path.parent / "controls.json").write_text(output + "\n")
    print(output)


if __name__ == "__main__":
    main()
