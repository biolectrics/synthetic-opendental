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

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--patients` | 750 | Number of patients to generate |
| `--city` | Random | Target city for addresses |
| `--state` | Random | Target state (required if --city used) |
| `--seed` | 42 | Random seed for reproducibility |
| `--output` | synthetic_data.sql | Output file path |
| `--no-perio` | (off) | Skip periodontal charting and treatment generation |
| `--stage` | (off) | **Test corner case** — force all periodontitis to one stage (`I`–`IV`); see below |
| `--grade` | (off) | **Test corner case** — force all periodontitis to one grade (`A`–`C`); see below |

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

| Patients | SQL File Size | Records |
|----------|---------------|---------|
| 100 | ~9 MB | ~40,000 |
| 500 | ~43 MB | ~194,000 |
| 750 | ~67 MB | ~300,000 |
| 2,000 | ~174 MB | ~774,000 |

> Sizes grew substantially once full periodontal charting was added (each adult accrues many `periomeasure` rows across years of exams). Use `--no-perio` for a much smaller dump if you don't need perio data.

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

### Schema Compatibility

Tested with Open Dental versions 22.x and 23.x. The generator outputs standard MySQL INSERT statements using column lists, so it should work with most versions.

### Primary Key Strategy

All generated primary keys start at 10,000+ to avoid collisions if you load the data into an existing database with some records.

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
