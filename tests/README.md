# QA checks

These scripts validate the generated SQL — both the schema/encoding correctness and
the clinical realism of the periodontal model — by parsing a generated `.sql` dump (no
MySQL required).

## Run everything

```bash
# uses $PYTHON or python3; point it at your venv if needed
PYTHON=./.venv/bin/python tests/run_qa.sh
```

This generates fixtures (default mode, the `--stage`/`--grade` corner cases, a `--no-medical`
smoke fixture, and a larger `--labels`/`--fidelity-report` fixture), asserts the capture flags
leave the SQL byte-identical and that `--no-medical` emits no medical tables, then runs the
checkers (`qa_validate`, `qa_flags`, `check_labels`, `check_medical`, `check_eligibility`,
`check_fidelity`) plus the `score_eligibility` demo, exiting non-zero on any failure.

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

**`check_medical.py <sql> <labels.json>`** — integrity of the structured medical-history
layer (`disease`/`medicationpat`/`allergy` + their def tables, written by default; disable with
`--no-medical`). Proves the tables are a trustworthy recruitment benchmark: FK integrity,
adults-only, def-table completeness/uniqueness, `medicationpat.RxCui` synced with its
`medication` def, `ProbStatus`/`DateStop` consistency, no future dates, every emitted row
represented in the labels, `documented ⊆ true` for conditions/meds/allergies, and clinical
coherence (pregnancy ⇒ female 18–45; tobacco/diabetes tie to the perio latents; COPD ⇒
ever-smoker; bisphosphonate ⇒ osteoporosis; methotrexate ⇒ RA; anticoagulant ⇒ AFib; current
and former smoker mutually exclusive).

**`check_eligibility.py <sql> <labels.json>`** — integrity of the OraFlow-US-003
`study_eligibility` answer key. Independently recomputes `qualifying_site_count` from the SQL
(`periomeasure` probing ≥4 mm co-located with a bleeding bit, in each patient's baseline exam)
and matches it to the label; verifies `natural_teeth`, the mobility exclusion, and the
procedure-based criteria (declined-SRP, recent SRP/surgery/prophy) against the SQL; and checks
the `eligible` flag and truth-based exclusions are internally consistent. Confirms a non-empty
eligible cohort exists.

**`score_eligibility.py <sql> <labels.json>`** — demonstration (informational, always exits 0):
runs a realistic *naive* SQL screening query and scores its **recall/precision against the
answer key**, then breaks down the false positives by the criteria the query could not see
(stage/grade, undocumented tobacco, uncontrolled disease in a free-text note, …). Shows why an
incomplete problem list inflates the candidate pool.

**`check_fidelity.py <fidelity.json>`** — CI gate on the generator's statistical-fidelity
report (`generate.py --fidelity-report`). Exits non-zero if any **gated** metric drifts
outside its (sampling-aware) tolerance: cohort stage mix vs the model-expected distribution,
periodontitis grade mix + monotone Grade-C-by-stage, smoker/diabetic/compliance prevalence,
RBL bands and the III/IV apical-third split, per-stage SRP utilization, recall-cadence
spread, the treated trajectory split (Hirschfeld & Wasserman reference), and the untreated
A≤B≤C progression ordering. Low-N per-stage cells are reported as *informational*. The
generator owns the fidelity logic; this script just enforces its verdict. The medical-history
metrics (condition prevalences, problem-list documentation sensitivity, medication coverage,
diabetes/tobacco latent tie-ins, penicillin-allergy prevalence) flow through the same gate.
