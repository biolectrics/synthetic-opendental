# Synthetic Open Dental Database

Generate realistic synthetic data for [Open Dental](https://www.opendental.com/) MySQL databases. Zero real patient information — all names, SSNs, addresses, and clinical details are computer-generated.

## Why This Exists

If you've ever tried to get test data for Open Dental, you know the options are limited:

- **Real patient data** — PHI/HIPAA nightmare, obviously not an option
- **Open Dental's built-in trial database** — Uses fake "T-codes" instead of real ADA codes, which breaks most real-world testing
- **Manual data entry** — Tedious and doesn't scale

This generator creates **realistic synthetic data** with actual ADA D-codes, proper fee ranges, insurance carriers, treatment history, and all the relationships between tables that make Open Dental's schema complex.

## What's Included

The generated database includes interconnected records across all major Open Dental tables:

| Table | Description |
|-------|-------------|
| `patient` | Demographics, contact info, guarantor relationships |
| `appointment` | Scheduled and completed visits with proper patterns |
| `procedurelog` | Procedures with real ADA codes (D0120, D1110, D2740, etc.) |
| `procedurecode` | Code definitions and descriptions |
| `provider` | Dentists and hygienists |
| `operatory` | Treatment rooms |
| `carrier` | Insurance companies (Delta, MetLife, Cigna, etc.) |
| `insplan` | Insurance plan details |
| `inssub` | Subscriber information |
| `patplan` | Patient-to-plan assignments |
| `claimproc` | Insurance estimates and payments |
| `payment` | Patient payments |
| `paysplit` | Payment allocations |
| `recall` | Hygiene recall tracking |
| `commlog` | Communication history |
| `procnote` | Clinical notes |
| `perioexam` | Periodontal charting sessions |
| `periomeasure` | Per-tooth, per-site perio measurements (probing, recession, bleeding, etc.) |
| `diseasedef` / `disease` | Problem-list definitions (real ICD-10 + SNOMED) and per-patient problems |
| `medication` / `medicationpat` | Medication catalog (real RxNorm RxCui) and per-patient prescriptions |
| `allergydef` / `allergy` | Allergen definitions and per-patient allergies |
| `definition` | Reference data for dropdowns |

### Data Characteristics

- **Age distribution** matching US dental patient demographics
- **53% have dental insurance** with realistic carrier mix
- **76% have unscheduled treatment** (treatment planned procedures)
- **~26% overdue for hygiene** appointments
- **Realistic fee ranges** based on ADA fee surveys
- **3 years of visit history** with seasonal patterns
- **Family accounts** with guarantor relationships
- **Longitudinal periodontal charting** for adults, staged/graded per the 2017 classification (see below)
- **Structured medical history** for adults — problem list, medications, and allergies at roughly NHANES-plausible, age/sex-conditioned prevalences, with **realistic documentation gaps** (see [Medical history](#medical-history-problems-medications-allergies))
- **Contact-channel preferences** (`PreferContactMethod`/`PreferConfirmMethod`/`PreferRecallMethod`) for recruitment reachability

## Quick Start

### Installation

**Requires Python 3.10+** (the generator uses `X | None` type-union syntax).

```bash
git clone https://github.com/dentaljosh/synthetic-opendental.git
cd synthetic-opendental
pip install -r requirements.txt
```

### Generate Data

```bash
# Default: 750 patients, random US city
python generate.py

# Custom patient count
python generate.py --patients 500 --output my_data.sql

# Specific city
python generate.py --city "Chicago" --state "IL"

# Reproducible output (same seed = same data)
python generate.py --seed 12345
```

### Load Into MySQL

```bash
# Connect to your Open Dental database
mysql -u root -p opendental < synthetic_data.sql
```

> **Note:** The generated SQL uses `SET FOREIGN_KEY_CHECKS = 0` at the start to allow loading in any order. Foreign key checks are re-enabled at the end.

> **Large datasets:** The SQL is **streamed to disk phase-by-phase** as it is generated, so memory stays bounded no matter how many patients you request. For runs of **more than 1000 patients** the writer automatically emits **batched multi-row `INSERT`s** (up to 500 rows per statement) — a substantial speedup for both generation and the MySQL load. The data is identical either way; at ≤1000 patients the output stays single-row (and byte-identical to older versions), so reproducible fixtures are unaffected. No flags needed — it's automatic.

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--patients` | 750 | Number of patients to generate |
| `--city` | Random | Target city for addresses |
| `--state` | Random | Target state (required if --city used) |
| `--seed` | 42 | Random seed for reproducibility |
| `--output` | synthetic_data.sql | Output file path |
| `--no-perio` | (off) | Skip periodontal charting and treatment generation |
| `--no-medical` | (off) | Skip [structured medical history](#medical-history-problems-medications-allergies) (problem list, medications, allergies) |
| `--stage` | (off) | **Test corner case** — force all periodontitis to one stage (`I`–`IV`); see below |
| `--grade` | (off) | **Test corner case** — force all periodontitis to one grade (`A`–`C`); see below |
| `--labels PATH` | (off) | Write the [ground-truth labels sidecar](#ground-truth-labels---labels) (JSON) alongside the SQL |
| `--fidelity-report [PATH]` | (off) | Print a [statistical-fidelity report](#statistical-fidelity-report---fidelity-report); optionally also write it as JSON |

## Supported Metro Areas

The generator includes realistic ZIP codes for these cities:

- New York, NY
- Los Angeles, CA
- Chicago, IL
- Houston, TX
- Phoenix, AZ
- Philadelphia, PA
- San Antonio, TX
- San Diego, CA
- Dallas, TX
- Seattle, WA
- Nashville, TN
- Omaha, NE
- Cleveland, OH
- Columbus, OH
- Cincinnati, OH
- Boston, MA
- Detroit, MI
- The Woodlands, TX
- Brentwood, TN

If you specify a city/state not in this list, the generator will create plausible random ZIP codes. (`--city` and `--state` must be supplied together.)

## Example Output Size

| Patients | SQL File Size | Records | `--labels` sidecar |
|----------|---------------|---------|--------------------|
| 100 | ~9 MB | ~40,000 | ~0.5 MB |
| 500 | ~43 MB | ~194,000 | ~2.6 MB |
| 750 | ~67 MB | ~300,000 | ~3.9 MB |
| 2,000 | ~174 MB | ~774,000 | ~10 MB |

> Sizes grew substantially once full periodontal charting was added (each adult accrues many `periomeasure` rows across years of exams). Use `--no-perio` for a much smaller dump if you don't need perio data. The optional `--labels` sidecar (per-site true CAL for every exam, plus the medical answer key) is off by default; its size scales with the perio data (roughly 6% of the SQL). The medical-history layer adds a few thousand small rows (problems/medications/allergies) — a rounding error next to the perio measurements; use `--no-medical` to omit it.

## Use Cases

- **Development & Testing** — Test queries, reports, and integrations against realistic data
- **Demos** — Show software to prospective customers without PHI concerns
- **Training** — Teach staff on Open Dental without risking real patient data
- **AI/ML Development** — Train models on dental data patterns
- **Load Testing** — Stress test systems with configurable data volumes

## Sample File

The `examples/` directory includes a pre-generated 500-patient database you can use immediately:

```bash
mysql -u root -p opendental < examples/sample_500_patients.sql
```

## Technical Details

### ADA Codes Used

The generator includes 40+ real ADA D-codes covering:

- Exams (D0120, D0140, D0150, D0180)
- X-rays (D0210, D0274, D0330, D0367)
- Cleanings (D1110, D1120, D1206)
- Perio (D4341, D4342, D4910, D4355, D4260, D4261, D4381)
- Fillings (D2140, D2391-D2394, D2330-D2331)
- Crowns (D2740, D2750, D2950)
- Extractions (D7140, D7210, D7220-D7240)
- Implants (D6010, D6056, D6058)
- Endo (D3310, D3320, D3330)
- Ortho (D8080, D8090, D8670)

### Periodontal Charting & Treatment

Adults (18+) receive longitudinal periodontal data modeled on the **2017 World Workshop classification** and US epidemiology:

- **Staging (I–IV) and grading (A–C)** assigned with age-stratified prevalence (NHANES/Eke); smoking and diabetes shift severity and progression rate. ~30–35% of adults end up as periodontitis cases, matching typical practice hygiene benchmarks.
- **Stage is driven by clinical attachment loss (CAL), not probing depth** — faithful to the 2017 system, where stage = interdental CAL at the worst site (I: 1–2 mm, II: 3–4 mm, III/IV: ≥5 mm) and probing depth is only a *complexity* descriptor (Tonetti, Greenwell & Kornman 2018). The model samples per-site CAL plus a gingival-margin position, and **derives probing depth** as `PD = CAL − GingMargin`. Because the margin can sit coronal to the CEJ from inflammatory swelling (a *pseudopocket*), a lower-stage patient can legitimately show **isolated deep pockets ≥6 mm** while CAL — and therefore the stage — stays in range. Deep pockets are kept localized (interproximal/molar), as in real Stage II cases.
- **Radiographic bone loss (RBL)** is modeled as a co-determinant of stage (% of root length): I <15% and II 15–33% (coronal third), III to the middle third, IV to the apical third. **Stage III vs IV is determined by whether RBL reaches the apical third** (≥60%), consistent with tooth-loss counts — not by CAL alone. Open Dental's perio schema has no structured bone-loss field, so the value is recorded in each `perioexam`'s `Note` (e.g. *"Radiographic bone loss ~45% of root length (middle third)."*).
- **Per-tooth, 6-site charting** in the Open Dental `perioexam` / `periomeasure` tables, using the real `PerioSequenceType` encoding: probing depth (4), gingival margin (2; coronal/negative margins are stored with Open Dental's 100+ encoding), MGJ (3), bleeding/suppuration/plaque/calculus bitmask (6), mobility (0), furcation (1). CAL itself is left for Open Dental to compute (it is never stored).
- **Longitudinal trajectories**, not single snapshots: each later exam *evolves from the previous one*. Worsening is real attachment loss (CAL up, the irreversible progression grade governs, concentrated at already-diseased sites); scaling & root planing produces a realistic pocket reduction split between attachment gain and resolution of inflammatory swelling (Cobb 2002); maintenance holds compliant patients near-arrested while non-compliant/Grade-C patients drift downhill. Cohort-wide this reproduces the ~80% stable / ~15% slow-downhill / ~5% extreme-downhill split (Hirschfeld & Wasserman 1978, DOI 10.1902/jop.1978.49.5.225).
- **Coherent treatment course**: comprehensive perio eval → SRP by quadrant (D4341/D4342) → re-evaluation → periodontal maintenance (D4910), with a literature-based fraction proceeding to osseous surgery (D4260/D4261) and adjunctive localized antimicrobial (D4381). Disable with `--no-perio`.
- **Individualized maintenance recall**: the D4910 interval is *not* a fixed 3 months for everyone. It is re-decided at each visit from current risk (worst-site CAL stage, grade, smoking/diabetes, residual ≥5 mm pockets, compliance) per the Lang & Tonetti Periodontal Risk Assessment and the AAP/EFP grade mapping — roughly **6 months (low risk) → 4 (moderate) → 3 (high) → 2 (very high)**, with scheduling jitter and a ~3-month post-SRP insurance floor. It tightens when disease recurs and lengthens when stable; severe recurrence re-enters active therapy (re-SRP).

> **Modeling note:** Open Dental's perio schema stores no structured radiographic-bone-loss value, so the modeled RBL percentage is surfaced in each `perioexam`'s free-text `Note` rather than a dedicated column. Stage III vs IV is driven by RBL extent (apical- vs middle-third) together with tooth loss, per the 2017 thresholds.

#### Test corner-case flags: `--stage` and `--grade`

By default the data reflects the **realistic distribution and progression** of disease in both stage and grade, as the literature suggests. The `--stage` and `--grade` flags are **deliberately non-realistic test corner cases** for exercising specific Open Dental functionality against a controlled cohort:

- **`--stage <I|II|III|IV>`** — every periodontitis patient is fixed at that single stage, with **CAL held strictly within that stage's band for the patient's entire history** (e.g. `--stage II` keeps interdental CAL ≤4 mm and never progresses into Stage III). Probing depth is left free, so a `--stage II` cohort still shows realistic isolated deep pseudopockets (≥6 mm) — only the *stage* (CAL) is pinned. Treatment procedures (SRP, maintenance, etc.) are still recorded. Grades still vary across patients.
- **`--grade <A|B|C>`** — every periodontitis patient is fixed at that single grade (e.g. `--grade A` keeps everyone Grade A). Stages still vary; progression follows that grade's rate.
- The two combine (`--stage III --grade C`). Healthy patients are still generated in both modes (only diseased patients are locked). These flags only affect periodontal data and are ignored under `--no-perio`.

### Medical history (problems, medications, allergies)

Real study-eligibility screening is mostly *medical* — diabetes, tobacco status, bisphosphonates (MRONJ risk), anticoagulants, immunosuppression, pregnancy, penicillin allergy — so the generator emits a structured problem list (`disease` with real ICD-10 + SNOMED codes), medications (`medicationpat` with real RxNorm RxCui), and allergies (`allergy`) for every adult. Diabetes and tobacco reuse the periodontal risk latents, so the coupling between systemic disease and periodontitis is real (e.g. diabetic smokers cluster in the worse perio stages).

The catalog is ~21 conditions and ~25 medications at roughly NHANES-plausible, age/sex-conditioned prevalences, with conditional bumps (diabetes raises hypertension; COPD only in ever-smokers; osteoporosis skews to older women; pregnancy only in women 18–45).

**Documentation gaps are modeled on purpose.** Real EHR problem lists are incomplete (Wright et al. 2015 measured 60–99% completeness across sites) while med and allergy lists are better but still imperfect (Kaboli et al. 2004). So each true condition is written to the problem list only with its per-condition sensitivity, each true prescription with ~95% probability, each true allergy with ~75%. The **ground truth is preserved in `--labels`** (`true_conditions` vs `documented_conditions`, etc.), which makes this a **labeled recruitment benchmark**: a patient-mining query only sees the documented rows, so you can score its recall and precision against the answer key.

This is why it's useful for **mining prospective patients for a research study** — you can prototype and *validate* an eligibility screener against data where the correct answer is known. Example: find candidate subjects who are documented diabetic smokers with Stage III–IV periodontitis and no penicillin allergy:

```sql
SELECT p.PatNum
FROM patient p
JOIN disease d_dm  ON d_dm.PatNum = p.PatNum
JOIN diseasedef dd_dm ON dd_dm.DiseaseDefNum = d_dm.DiseaseDefNum AND dd_dm.Icd10Code LIKE 'E11%'
JOIN disease d_tob ON d_tob.PatNum = p.PatNum
JOIN diseasedef dd_tob ON dd_tob.DiseaseDefNum = d_tob.DiseaseDefNum AND dd_tob.Icd10Code = 'F17.210'
WHERE d_dm.ProbStatus = 0
  AND NOT EXISTS (                       -- exclude documented penicillin allergy
      SELECT 1 FROM allergy a
      JOIN allergydef ad ON ad.AllergyDefNum = a.AllergyDefNum
      WHERE a.PatNum = p.PatNum AND ad.Description = 'Penicillin' AND a.StatusIsActive = 1);
```

(Perio stage is not stored in Open Dental — join the `--labels` `profile.true_stage`, or infer it from CAL, to add the Stage III–IV filter.) Because the label file carries the true diabetics and smokers, you can measure exactly how many eligible patients this query *missed* because their diabetes was never charted. `--no-medical` turns the whole layer off; it is skipped automatically under `--no-perio` (it reads the perio latents).

### OraFlow-US-003 eligibility benchmark

The medical + perio layers are tuned so the dataset can be **scored against a real study protocol** — the Biolectrics OraFlow-US-003 Confirmatory Study (adults with Periodontitis Stage I–III Grade A/B, ≥8 sites with BOP + PD ≥4 mm, who decline SRP). When `--labels` is set, every adult record carries a **`study_eligibility`** answer key evaluating all 9 inclusion + 19 exclusion criteria against ground truth:

```jsonc
"study_eligibility": {
  "protocol": "OraFlow-US-003 v13",
  "eligible": false,
  "qualifying_site_count": 11,          // CURRENT-exam sites with BOP AND PD>=4mm (gate IC3)
  "natural_teeth": 27,
  "true_stage": "II", "true_grade": "B",
  "failed_inclusion": [],
  "triggered_exclusion": ["EX9_tobacco"],   // criterion keys that disqualify
  "on_antibacterial_rinse": false,
  "not_evaluable": ["IC6_rinse_consent","EX4_amalgam_margin", ...]   // consent/unmodeled
}
```

To make the protocol's criteria queryable, v0.5.0 added the signals a recruitment screen depends on: a **declined-SRP recruitment pool** (a treatment-planned but never-completed D4341/D4342 for periodontitis patients who forgo SRP), **systemic antibiotics** and **antibacterial rinses** with dates (the 3-month look-back for EX13 / the rinse switch for IC6), **anticoagulants incl. clopidogrel**, **cancer / pacemaker / prosthetic heart valve / TMD** conditions, and a controlled-vs-uncontrolled status on diabetes/HTN/cancer (written to the problem note; only *uncontrolled* disqualifies).

Because a screening query only sees the *documented* SQL while the answer key holds the truth, you can score the query end-to-end. `tests/score_eligibility.py` runs a realistic naive query and reports it:

```
truly eligible (answer key): 23
recall    = 1.000    (every eligible subject found)
precision = 0.561    (~44% of candidates are actually ineligible)
18 false positives — criteria the naive query could not see:
  IC2_stage_grade   7     # stage/grade isn't stored in Open Dental
  EX9_tobacco       4     # undocumented tobacco use
  EX12_hyperplasia_med 4  # gingival-hyperplasia drug, not flagged
  EX13_antibiotics  3     # recent antibiotic course
  ...
```

That precision gap is the real recruitment risk — wasted screening visits on patients who turn out ineligible — and the answer key quantifies exactly which criteria a smarter query must recover. `tests/check_eligibility.py` proves the key describes the SQL: it recomputes `qualifying_site_count` directly from the `periomeasure` bleeding + probing rows and matches it to every label.

### Ground-truth labels (`--labels`)

The generator is, under the hood, a **generative model with fully known latent state**: for every patient it chooses a true stage/grade/bone-loss and tracks a noise-free floating-point CAL at every site, then rounds, clamps, and encodes only the *observable* records into the SQL — discarding the truth. Real clinics never have that truth, so no dataset built from real EHRs can carry it. `--labels PATH` persists it as a JSON **answer key** that joins to the SQL, turning the dump from "realistic-looking data" into a **labeled benchmark** you can train *and objectively score* models against (2017 staging classifiers, attachment-loss progression predictors, treatment-response models, and measurement-error / examiner-variability models via true CAL vs emitted probing).

```bash
python generate.py --patients 750 --seed 42 --labels labels.json --output data.sql
```

The file is a single JSON object:

```jsonc
{
  "meta": { "schema_version": 3, "seed": 42, "generated_date": "...",
            "flags": {...}, "citations": [...], "label_definitions": {...} },
  "patients": [{
    "PatNum": 10412, "age": 57, "charted": true,
    "profile": { "true_stage": "III", "true_grade": "C", "smoker": true,
                 "bone_loss_pct": 47, "rbl_third": "middle",
                 "teeth_present_baseline": [...], "teeth_lost_to_perio": [...] },
    "trajectory": { "class": "downhill", "annual_mean_cal_mm": 0.31,
                    "treatment_response": "partial", "n_exams": 6, ... },
    "medical": {
      "true_conditions": [{ "key": "t2dm", "icd10": "E11.9", "snomed": "44054006", "onset": "2019-08-02" },
                          { "key": "htn",  "icd10": "I10",   "snomed": "38341003", "onset": "..." }],
      "documented_conditions": [{ "key": "t2dm", "DiseaseNum": 10188, "icd10": "E11.9" }],
      "true_medications": [{ "key": "metformin", "rx_for": "t2dm", "rxcui": 6809 }],
      "documented_medications": [{ "key": "metformin", "MedicationPatNum": 10233, "RxCui": 6809 }],
      "true_allergies": ["penicillin"], "documented_allergies": [{ "key": "penicillin", "AllergyNum": 10041 }],
      "contact": { "prefer_contact_method": 8, "txt_msg_ok": 1 }
    },
    "exams": [{ "PerioExamNum": 10042, "ExamDate": "2024-03-11", "visit_type": "reeval",
                "stage_at_visit": "III", "worst_true_cal_mm": 6.1, "risk_tier": "high",
                "teeth": { "14": { "true_cal_mm": [5.8, 6.1, 5.9, 4.2, 4.0, 4.3],
                                   "observed_pd_mm": [5, 6, 6, 4, 4, 4],
                                   "recession_mm": [...], "swell": [...] } } }]
  }]
}
```

- **Join key:** each exam's `PerioExamNum` + tooth number map to the SQL `periomeasure` rows (`SequenceType 4` = probing). `observed_pd_mm` equals the emitted probing exactly; `true_cal_mm` is the noise-free CAL behind it (the emitted CAL = `round(true_cal)`). In the `medical` block, `DiseaseNum` / `MedicationPatNum` / `AllergyNum` join to the `disease` / `medicationpat` / `allergy` tables.
- **Derived labels** (`trajectory.class`, `annual_mean_cal_mm`, `treatment_response`) are computed from the whole-mouth mean true CAL and deep-pocket closure — the clinical longitudinal measures — not from any single noisy site.
- **Medical truth vs documentation:** `documented_*` is always a subset of `true_*`. The gap is deliberate (see [Medical history](#medical-history-problems-medications-allergies)), so you can score a patient-screening query's **recall and precision** — the documented rows are what a query finds, the `true_*` set is the answer key.
- Adults who are profiled but not charted (e.g. a healthy patient not selected for screening) appear with `"charted": false` and a null trajectory; minors (no perio) are omitted. Off by default; ignored under `--no-perio`. `schema_version` is `3` (v0.5.0 added the `medical` block in v2 and the `study_eligibility` answer key in v3 — see [the OraFlow-US-003 eligibility benchmark](#oraflow-us-003-eligibility-benchmark)).

### Statistical-fidelity report (`--fidelity-report`)

Proves the generated cohort actually matches the epidemiology it claims to model. `--fidelity-report` prints an observed-vs-literature table; add a path to also write it as machine-readable JSON (consumed by the CI gate in `tests/`).

```bash
python generate.py --patients 1000 --seed 42 --fidelity-report fidelity.json --output data.sql
```

Each gated metric compares the cohort against the model's literature targets with a **sampling-noise-aware tolerance** (so it is robust across seeds yet still catches real drift): stage mix vs the exact model-expected distribution; periodontitis grade mix and a monotone Grade-C-by-stage rise; smoker/diabetes/compliance prevalence; radiographic-bone-loss bands and the III/IV apical-third split; per-stage SRP utilization and "healthy get no SRP"; individualized recall cadence; the treated-cohort stable/downhill/extreme trajectory split (Hirschfeld & Wasserman reference); and the untreated **A ≤ B ≤ C** progression ordering. When the medical-history layer is on, it also gates the well-powered condition prevalences (hypertension, hyperlipidemia, tobacco, GERD, diabetes, osteoarthritis, depression, anxiety, asthma), the pooled **problem-list documentation sensitivity** and medication coverage, the diabetes/tobacco latent tie-ins, and penicillin-allergy prevalence. Low-N per-stage cells and rare conditions are reported as *informational*. Under `--stage`/`--grade` locks the distribution and progression metrics automatically become informational (the cohort is deliberately non-representative).

### Schema Compatibility

Tested with Open Dental versions 22.x and 23.x. The generator outputs standard MySQL INSERT statements using column lists, so it should work with most versions.

### Primary Key Strategy

All generated primary keys start at 10,000+ to avoid collisions if you load the data into an existing database with some records. This includes the medical-history definition tables (`diseasedef`/`medication`/`allergydef`), which start at 10,000 rather than the low starting points a fresh Open Dental install uses — real practices routinely carry well over 100 such rows, so a low start would risk collisions.

## Built By

This tool was created by the team at **[Luna](https://yourluna.co)** — a natural language interface for dental practice data.

If you're a dental practice looking to query your Open Dental data using plain English (like "Show me patients overdue for hygiene" or "What was our production last month?"), [join our waitlist](https://yourluna.co).

## Contributing

Issues and pull requests welcome. Some ideas for contributions:

- Additional procedure codes
- More metro areas with accurate ZIP codes
- Support for multi-clinic setups
- Additional table coverage (claims, referrals, etc.)

## License

MIT License — use this however you want. See [LICENSE](LICENSE) for details.

---

**Disclaimer:** This tool generates synthetic data only. It has no affiliation with Open Dental Software Inc. Open Dental is a trademark of Open Dental Software Inc.
