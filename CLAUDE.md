# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-file Python generator (`generate.py`) that emits a MySQL `.sql` dump of **synthetic** [Open Dental](https://www.opendental.com/) dental-practice data — zero real PHI. The point of existence is that Open Dental's own trial DB uses fake "T-codes"; this tool uses **real ADA D-codes mapped to the real `CodeNum` integers from an actual Open Dental database** so the output works against real-world queries and integrations.

## Commands

```bash
pip install -r requirements.txt          # only dependency: faker>=18.0.0

python generate.py                       # 750 patients, random metro, seed 42 -> synthetic_data.sql
python generate.py --patients 500 --output data.sql
python generate.py --city "Chicago" --state "IL"   # --state required when --city is given
python generate.py --seed 12345          # reproducible

mysql -u root -p opendental < synthetic_data.sql   # load into a real OD database
mysql -u root -p opendental < examples/sample_500_patients.sql  # pre-generated sample
```

There is **no build, test suite, or linter** — the repo is the one script plus a sample dump. To "verify" a change, run the generator and load the SQL into MySQL (or grep the output). Generated `*.sql` files are gitignored except `examples/*.sql`.

## Architecture

Everything lives in `generate.py`. Top ~480 lines are module-level **lookup/config tables**; the rest is one class, `SyntheticDataGenerator`, plus `main()`.

**Two-phase flow inside the class:** each `_generate_*` / `_create_*` method (1) builds an in-memory `dict` record, appends it to a `self.<table>` list (e.g. `self.patients`, `self.appointments`), AND (2) appends a SQL string to `self.sql_statements` via the `generate_insert(table, columns, values)` helper. The in-memory lists exist so later tables can reference earlier rows' keys. `main()` writes the header, `SET FOREIGN_KEY_CHECKS = 0`, every statement, then `SET FOREIGN_KEY_CHECKS = 1`.

**FK-ordered generation is load-bearing.** `generate_all()` calls the generators in dependency order: base reference data → providers → operatories → carriers → insplans → patients → inssubs/patplans → appointments+procedures → recalls → commlogs → payments. A child record reads its parent's already-assigned PK from the parent list, so reordering these calls will produce dangling references.

**Primary-key counters.** `__init__` sets per-table `self.next_*_num` counters; most start at **10000** (carriers/insplans/providers/operatories at **100**). They start high so the dump can be loaded into an existing OD database without colliding with real rows. Counters only ever increment — never reuse a value.

**Determinism.** `__init__` seeds **both** `random.seed(seed)` and `Faker.seed(seed)`. Same `--seed` + same args ⇒ identical data. Any new code that consumes `random` or `self.fake` must run in a deterministic order (no set iteration, no dict-ordering assumptions across Python versions) or it breaks reproducibility. The only nondeterministic byte is the `datetime.now()` timestamp in the file header.

## Domain rules to preserve

- **Real ADA code mapping is mandatory.** A procedure code is only emitted if it exists in BOTH `PROCEDURE_CODES` (definition + fee range + category) AND `REAL_CODE_TO_CODENUM` (ADA code → real OD `CodeNum`). `__init__` silently drops any `PROCEDURE_CODES` entry with no `CodeNum` mapping. To add a code, edit both structures.
- **`*_DEFNUMS` constants** (`BILLING_TYPE_DEFNUMS`, `PAYMENT_TYPE_DEFNUMS`, `PROC_CAT_DEFNUMS`) are real `definition.DefNum` values from Open Dental — don't invent them.
- **Statistical targets are intentional**, tuned by probabilities scattered through the generators: ~94% solo vs family patients (`_generate_patients`), ~53% insured, ~76% with treatment-planned procedures, ~26% overdue for hygiene, ~20% with a future appointment, plus a US dental `AGE_DISTRIBUTION`. Changing a magic probability shifts a documented characteristic in the README — keep them in sync.
- **Families share a guarantor**: the head of household is its own guarantor (`Guarantor == PatNum`); members point at the head's `PatNum`, and insurance subscribers usually resolve to the guarantor.
- **Metro areas**: `METRO_AREAS` carries real ZIP codes for 10 cities. An unrecognized `--city/--state` synthesizes 20 random ZIPs instead.
