#!/usr/bin/env bash
# Compile and fit ic2_glue.pld for the ATF1502AS with WinCUPL + the Atmel fitter, inside the
# dinoboards/cpld-toolchain Docker image. Writes ic2_glue.jed (to program) and ic2_glue.fit
# (fitter report: pinout, macrocells). The logic itself is checked by tools/check_cpld.py.
set -e
cd "$(dirname "$0")"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
cp ic2_glue.pld "$work/"
MSYS_NO_PATHCONV=1 docker run --rm -v "$(cd "$work" && pwd -W 2>/dev/null || pwd):/work" \
    dinoboards/cpld-toolchain:latest cupld ic2_glue
grep -q 'fits; JTAG ON' "$work/bin/ic2_glue.fit"
cp "$work/bin/ic2_glue.jed" "$work/bin/ic2_glue.fit" .
echo "ic2_glue.jed: $(grep -o 'Total Macro cells used.*' ic2_glue.fit)"
