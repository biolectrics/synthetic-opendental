#!/usr/bin/env bash
# Generate fixtures with the generator, then run the default-mode and flag-mode QA
# checks against them. Exits non-zero on any failure (CI-friendly).
#
#   PYTHON=./.venv/bin/python tests/run_qa.sh     # use a specific interpreter
#   tests/run_qa.sh                                # uses $PYTHON or python3
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
PY="${PYTHON:-python3}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo ">> Generating fixtures with $PY ..."
"$PY" "$ROOT/generate.py" --patients 300 --seed 42                 --output "$TMP/default.sql" >/dev/null
"$PY" "$ROOT/generate.py" --patients 200 --seed 42 --stage II      --output "$TMP/stage2.sql"  >/dev/null
"$PY" "$ROOT/generate.py" --patients 200 --seed 42 --stage III --grade C --output "$TMP/stage3C.sql" >/dev/null
"$PY" "$ROOT/generate.py" --patients 200 --seed 42 --grade A       --output "$TMP/gradeA.sql"  >/dev/null
"$PY" "$ROOT/generate.py" --patients 200 --seed 42 --grade C       --output "$TMP/gradeC.sql"  >/dev/null
# Larger fixture with the ground-truth labels sidecar + fidelity report (distribution checks
# need adequate N to be meaningful).
"$PY" "$ROOT/generate.py" --patients 800 --seed 42 \
    --labels "$TMP/labels.json" --fidelity-report "$TMP/fidelity.json" \
    --output "$TMP/fidelity.sql" >/dev/null

echo ">> Default-mode checks:"
"$PY" "$HERE/qa_validate.py" "$TMP/default.sql"
echo ">> Flag-mode checks:"
"$PY" "$HERE/qa_flags.py" "$TMP"
echo ">> Labels integrity (labels JSON vs emitted SQL):"
"$PY" "$HERE/check_labels.py" "$TMP/fidelity.sql" "$TMP/labels.json"
echo ">> Statistical-fidelity gate (cohort vs literature):"
"$PY" "$HERE/check_fidelity.py" "$TMP/fidelity.json"

echo ">> ALL QA PASSED"
