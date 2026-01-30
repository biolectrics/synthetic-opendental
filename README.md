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
| `definition` | Reference data for dropdowns |

### Data Characteristics

- **Age distribution** matching US dental patient demographics
- **53% have dental insurance** with realistic carrier mix
- **76% have unscheduled treatment** (treatment planned procedures)
- **~26% overdue for hygiene** appointments
- **Realistic fee ranges** based on ADA fee surveys
- **3 years of visit history** with seasonal patterns
- **Family accounts** with guarantor relationships

## Quick Start

### Installation

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

If you specify a city/state not in this list, the generator will create plausible random ZIP codes.

## Example Output Size

| Patients | SQL File Size | Records |
|----------|---------------|---------|
| 100 | ~3 MB | ~25,000 |
| 500 | ~15 MB | ~125,000 |
| 750 | ~22 MB | ~185,000 |
| 2,000 | ~60 MB | ~500,000 |

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
- Perio (D4341, D4342, D4910, D4355)
- Fillings (D2140, D2391-D2394, D2330-D2331)
- Crowns (D2740, D2750, D2950)
- Extractions (D7140, D7210, D7220-D7240)
- Implants (D6010, D6056, D6058)
- Endo (D3310, D3320, D3330)
- Ortho (D8080, D8090, D8670)

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
