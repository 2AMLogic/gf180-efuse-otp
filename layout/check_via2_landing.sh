#!/usr/bin/env bash
# Count via2 shapes with no M3 above or no M2 below them, per cell, with the
# pinned klt's klayout. Exit 1 if any cell has one. Default stream: layout/efuse_otp_array.gds.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=../signoff/klt.sh
. "$root/signoff/klt.sh"
klt_python -I "$root/layout/check_via2_landing.py" "${1:-$root/layout/efuse_otp_array.gds}"
