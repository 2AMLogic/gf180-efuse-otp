#!/usr/bin/env bash
# Build the exact Icarus Verilog and Yosys releases that verification/run.sh
# enforces (13.0 and 0.67) from their release tags into $PREFIX, checking the
# tagged commit. Stock ubuntu-latest packages are not these versions, and the
# version pin is not loosened to fit them. Skips a tool already present in
# $PREFIX (restored from the CI cache).
set -euo pipefail
PREFIX="${PREFIX:?set PREFIX}"
IVERILOG_REPO=https://github.com/steveicarus/iverilog
IVERILOG_TAG=v13_0
IVERILOG_COMMIT=dfeee909ed9f20b4870dd93423156c0170c0e1ff
YOSYS_REPO=https://github.com/YosysHQ/yosys
YOSYS_TAG=v0.67
YOSYS_COMMIT=2d1509d1bcb8df0723f6790057e3b1d21c876683

src="$(mktemp -d)"
trap 'rm -rf "$src"' EXIT

fetch() { # repo tag commit dest
  git clone --quiet --depth 1 --branch "$2" "$1" "$4"
  [ "$(git -C "$4" rev-parse HEAD)" = "$3" ] || { echo "$2: unexpected commit" >&2; exit 1; }
}

if [ ! -x "$PREFIX/bin/iverilog" ]; then
  fetch "$IVERILOG_REPO" "$IVERILOG_TAG" "$IVERILOG_COMMIT" "$src/iverilog"
  (cd "$src/iverilog" && sh autoconf.sh && ./configure --prefix="$PREFIX" >/dev/null \
    && make -j2 >/dev/null && make install >/dev/null)
fi

if [ ! -x "$PREFIX/bin/yosys" ]; then
  fetch "$YOSYS_REPO" "$YOSYS_TAG" "$YOSYS_COMMIT" "$src/yosys"
  git -C "$src/yosys" submodule update --init --recursive --depth 1 --quiet
  make -C "$src/yosys" -j2 PREFIX="$PREFIX" ENABLE_ABC=1 >/dev/null
  make -C "$src/yosys" PREFIX="$PREFIX" install >/dev/null
fi

"$PREFIX/bin/iverilog" -V | head -1
"$PREFIX/bin/yosys" -V
