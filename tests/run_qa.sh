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
# need adequate N to be meaningful). This fixture also carries the medical-history layer.
"$PY" "$ROOT/generate.py" --patients 800 --seed 42 \
    --labels "$TMP/labels.json" --fidelity-report "$TMP/fidelity.json" \
    --output "$TMP/fidelity.sql" >/dev/null
# --no-medical smoke fixture: must emit none of the six medical tables.
"$PY" "$ROOT/generate.py" --patients 100 --seed 42 --no-medical --output "$TMP/nomed.sql" >/dev/null

# Determinism guard: the capture/medical layers must not perturb the SQL relative to a
# plain run at the same seed EXCEPT for the appended labels/report -- i.e. --labels and
# --fidelity-report draw zero RNG, so the .sql is byte-identical with and without them.
"$PY" "$ROOT/generate.py" --patients 800 --seed 42 --output "$TMP/plain800.sql" >/dev/null
if ! diff -q <(grep -v '^-- Generated:' "$TMP/plain800.sql") \
             <(grep -v '^-- Generated:' "$TMP/fidelity.sql") >/dev/null; then
    echo "FAIL: --labels/--fidelity-report changed the SQL bytes (capture must be RNG-free)"; exit 1
fi
echo ">> Determinism guard: capture flags leave the SQL byte-identical  PASS"

echo ">> --no-medical smoke check:"
if grep -qE "INSERT INTO \`(diseasedef|disease|medication|medicationpat|allergydef|allergy)\`" "$TMP/nomed.sql"; then
    echo "FAIL: --no-medical still emitted medical tables"; exit 1
fi
echo "   no medical tables emitted under --no-medical  PASS"

echo ">> Default-mode checks:"
"$PY" "$HERE/qa_validate.py" "$TMP/default.sql"
echo ">> Flag-mode checks:"
"$PY" "$HERE/qa_flags.py" "$TMP"
echo ">> Labels integrity (labels JSON vs emitted SQL):"
"$PY" "$HERE/check_labels.py" "$TMP/fidelity.sql" "$TMP/labels.json"
echo ">> Medical-history integrity (problem list / meds / allergies):"
"$PY" "$HERE/check_medical.py" "$TMP/fidelity.sql" "$TMP/labels.json"
echo ">> Study-eligibility answer-key integrity (OraFlow-US-003):"
"$PY" "$HERE/check_eligibility.py" "$TMP/fidelity.sql" "$TMP/labels.json"
echo ">> Statistical-fidelity gate (cohort vs literature):"
"$PY" "$HERE/check_fidelity.py" "$TMP/fidelity.json"
echo ">> Eligibility scoring demo (naive query recall/precision vs answer key):"
"$PY" "$HERE/score_eligibility.py" "$TMP/fidelity.sql" "$TMP/labels.json"

echo ">> ALL QA PASSED"
