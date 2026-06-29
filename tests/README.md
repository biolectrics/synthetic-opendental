# QA checks

These scripts validate the generated SQL — both the schema/encoding correctness and
the clinical realism of the periodontal model — by parsing a generated `.sql` dump (no
MySQL required).

## Run everything

```bash
# uses $PYTHON or python3; point it at your venv if needed
PYTHON=./.venv/bin/python tests/run_qa.sh
```

This generates fixtures (default mode + the `--stage`/`--grade` corner cases) and runs
both checkers, exiting non-zero on any failure.

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
