# QA checks

These scripts validate the generated SQL — both the schema/encoding correctness and
the clinical realism of the periodontal model — by parsing a generated `.sql` dump (no
MySQL required).

## Run everything

```bash
# uses $PYTHON or python3; point it at your venv if needed
PYTHON=./.venv/bin/python tests/run_qa.sh
```

This generates fixtures (default mode, the `--stage`/`--grade` corner cases, and a larger
`--labels`/`--fidelity-report` fixture) and runs all four checkers, exiting non-zero on any
failure.

## Run a single checker

```bash
python generate.py --patients 300 --seed 42 --output /tmp/d.sql
python tests/qa_validate.py /tmp/d.sql        # default-mode: schema, encoding, longitudinal, cadence
```

```bash
for f in "--stage II" "--stage III --grade C" "--grade A" "--grade C"; do ... ; done  # see run_qa.sh
python tests/qa_flags.py /tmp/fixtures_dir    # flag-mode: stage bounded by CAL, deep pockets allowed, grade differential
```

## What they check

**`qa_validate.py`** (default mode) — among others:
- Every `INSERT` parses; only adults are charted; FK references resolve.
- `PerioSequenceType` usage and per-type encoding (Probing/GingMargin 100+ coronal
  encoding/MGJ maxillary-lingual rule/Bleeding bitmask/Mobility/Furcation; CAL never stored).
- `CAL = Probing + GingMargin` is consistent and non-negative; deep pockets and
  pseudopockets occur in the realistic mix.
- Treatment coherence (eval → SRP → D4910), no double-booked cleanings.
- Longitudinal coherence: healthy stay flat, treated show the post-SRP drop, cohort-wide
  better/stable/worse split is realistic.
- Maintenance recall is **individualized** (interval varies, multiple cadence tiers).

**`qa_flags.py`** (corner cases):
- `--stage X` bounds **CAL** to the stage band (never the next stage) while still allowing
  isolated deep pseudopockets; healthy patients are kept.
- `--grade A` progresses far less than `--grade C` (grade lock controls progression).

**`check_labels.py <sql> <labels.json>`** — integrity of the ground-truth labels sidecar
(written by `generate.py --labels`) against the emitted SQL. Proves the labels are a
trustworthy answer key: every labeled `observed_pd_mm` equals the SQL probing exactly, and
the stored CAL (probing + gingival margin) equals the labeled noise-free true CAL rounded to
the nearest mm — over *every* charted site. Also checks minors are absent, uncharted patients
are represented (`charted:false`, null trajectory), join coverage, and that each patient's
baseline stage matches the labeled true stage.

**`check_fidelity.py <fidelity.json>`** — CI gate on the generator's statistical-fidelity
report (`generate.py --fidelity-report`). Exits non-zero if any **gated** metric drifts
outside its (sampling-aware) tolerance: cohort stage mix vs the model-expected distribution,
periodontitis grade mix + monotone Grade-C-by-stage, smoker/diabetic/compliance prevalence,
RBL bands and the III/IV apical-third split, per-stage SRP utilization, recall-cadence
spread, the treated trajectory split (Hirschfeld & Wasserman reference), and the untreated
A≤B≤C progression ordering. Low-N per-stage cells are reported as *informational*. The
generator owns the fidelity logic; this script just enforces its verdict.
