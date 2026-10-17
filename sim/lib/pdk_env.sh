#!/usr/bin/env bash
# Resolve the pinned gf180mcu variant directory; refuse any other revision.
#
# Source it (exports PDK_ROOT, PDK_VARIANT_DIR, PDK_REVISION) or run it
# (prints the variant directory). The pin lives only in sim/pdk.json.
#
#   CIEL_ROOT   ciel root, default $HOME/.ciel
#
# Exit 0: tree found and its SOURCES revision equals the pin.
# Exit 1: pin unreadable, no tree found, or SOURCES at another revision.

_pdk_env_main() {
  local here pin variant root dir src
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  command -v jq >/dev/null || { echo "pdk_env: jq is required" >&2; return 1; }
  pin="$(jq -er .open_pdks_revision "$here/../pdk.json")" \
    && variant="$(jq -er .variant "$here/../pdk.json")" \
    || { echo "pdk_env: cannot read the pin from sim/pdk.json" >&2; return 1; }
  root="${CIEL_ROOT:-$HOME/.ciel}"
  dir="$root/ciel/gf180mcu/versions/$pin/$variant"
  if [[ ! -d "$dir" ]]; then
    echo "pdk_env: no tree for pinned revision $pin at $dir (CIEL_ROOT=$root); other trees are not used" >&2
    return 1
  fi
  src="$(cat "$dir/SOURCES" 2>/dev/null)"
  if [[ "$src" != "open_pdks $pin" ]]; then
    echo "pdk_env: $dir/SOURCES reads '${src:-<missing>}', expected 'open_pdks $pin'" >&2
    return 1
  fi
  PDK_ROOT="$root/ciel/gf180mcu/versions/$pin"
  PDK_VARIANT_DIR="$dir"
  PDK_REVISION="$pin"
  export PDK_ROOT PDK_VARIANT_DIR PDK_REVISION
}

if _pdk_env_main; then
  [[ "${BASH_SOURCE[0]}" == "$0" ]] && echo "$PDK_VARIANT_DIR"
  (return 0 2>/dev/null) && return 0 || exit 0
else
  (return 0 2>/dev/null) && return 1 || exit 1
fi
