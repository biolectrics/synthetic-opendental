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

python generate.py --labels labels.json           # + ground-truth answer key (JSON)
python generate.py --fidelity-report fidelity.json # + observed-vs-literature report (stdout + JSON)
python generate.py --no-medical                    # skip the medical-history layer

mysql -u root -p opendental < synthetic_data.sql   # load into a real OD database
mysql -u root -p opendental < examples/sample_500_patients.sql  # pre-generated sample

PYTHON=./.venv/bin/python tests/run_qa.sh          # generate fixtures + run the QA suite
```

**QA suite** lives in `tests/` (no pytest; the checkers parse the emitted `.sql`). `run_qa.sh` builds fixtures and runs: `qa_validate.py` (default-mode schema/clinical invariants, incl. medical-table FK/adults-only), `qa_flags.py` (`--stage`/`--grade` locks), `check_labels.py` (labels JSON provably describes the SQL), `check_medical.py` (medical tables vs labels: FK, documented⊆true, clinical coherence), and `check_fidelity.py` (the fidelity report's gated metrics). It also asserts the capture flags leave the SQL byte-identical and that `--no-medical` emits no medical tables. It exits non-zero on any failure — this is the regression gate. Otherwise, to spot-check a change, run the generator and grep the output or load it into MySQL. Generated `*.sql` files are gitignored except `examples/*.sql`.

## Architecture

Everything lives in `generate.py`. Top ~480 lines are module-level **lookup/config tables**; the rest is one class, `SyntheticDataGenerator`, plus `main()`.

**Two-phase flow inside the class:** each `_generate_*` / `_create_*` method (1) builds an in-memory `dict` record, appends it to a `self.<table>` list (e.g. `self.patients`, `self.appointments`), AND (2) appends a SQL string to `self.sql_statements` via the `generate_insert(table, columns, values)` helper. The in-memory `dict` lists always stay resident because later tables reference earlier rows' keys.

**Streaming + batched write.** `main()` opens the output file, writes the header + `SET FOREIGN_KEY_CHECKS = 0`, calls `generate_all(out=f)`, then writes `SET FOREIGN_KEY_CHECKS = 1`. `generate_all(out)` calls `self._flush()` after **every phase**: `_flush` writes that phase's `self.sql_statements` to `out` and clears the list, so the SQL-string buffer never holds the whole run (only the dict lists persist). Without `out` (the QA suite's in-memory callers) `_flush` is a no-op and the full list is returned — unchanged behavior.
- **Batched INSERTs (`>1000` patients only).** When streaming a run of more than 1000 patients, `_flush` coalesces each phase's rows into multi-row `INSERT INTO t (cols) VALUES (r1),(r2),…;` statements, `<= BATCH_ROWS` (500) rows each, grouped by the `table (cols) VALUES ` prefix. This is a big speedup for both generation and the MySQL load. It reuses the exact escaped value-tuples `generate_insert` produced, so the **data is identical** — only the statement packing changes; the per-table regrouping is safe because the dump loads under `FOREIGN_KEY_CHECKS = 0`. At `<= 1000` patients the output stays **single-row and byte-identical** to the pre-batch tool, so the QA byte-identical checks are unaffected.
- **Perf note:** recall generation pre-indexes appointments by `PatNum` (was an O(patients × appointments) double scan); do not reintroduce a full-list scan inside a per-patient loop.

**FK-ordered generation is load-bearing.** `generate_all()` calls the generators in dependency order: base reference data → providers → operatories → carriers → insplans → patients → inssubs/patplans → appointments+procedures → recalls → commlogs → payments. A child record reads its parent's already-assigned PK from the parent list, so reordering these calls will produce dangling references.

**Primary-key counters.** `__init__` sets per-table `self.next_*_num` counters; most start at **10000** (carriers/insplans/providers/operatories at **100**). They start high so the dump can be loaded into an existing OD database without colliding with real rows. Counters only ever increment — never reuse a value.

**Determinism.** `__init__` seeds **both** `random.seed(seed)` and `Faker.seed(seed)`. Same `--seed` + same args ⇒ identical data. Any new code that consumes `random` or `self.fake` must run in a deterministic order (no set iteration, no dict-ordering assumptions across Python versions) or it breaks reproducibility. The only nondeterministic byte is the `datetime.now()` timestamp in the file header.

**Ground-truth capture layer (`--labels` / `--fidelity-report`).** The perio module tracks a noise-free float CAL per site and knows each patient's true stage/grade/trajectory, but the SQL only carries the rounded, encoded *observable* rows. When either flag is set (`self._perio_capture`), `_emit_perio_exam` also appends a per-exam **snapshot** (per-site true CAL vs emitted probing, stage-at-visit, risk tier) to `self.perio_snapshots`, and `_finalize_perio_labels` assembles per-patient label records (attaching the profile and deriving trajectory class + treatment-response). `write_perio_labels` serializes them; `_perio_fidelity_report` / `_print_fidelity_report` compare the cohort against the module's literature-target constants.

- **This capture is pure observation — it draws ZERO `random`/`Faker` values** — so the `.sql` output is **byte-identical** whether or not the flags are set. This is an invariant: never let capture/report code consume RNG, or you desync every existing fixture and seed. (`tests/run_qa.sh` + a same-seed `diff` guard it.)
- Two samplers were split into pure "compute" + "draw" halves so the report can reuse the exact model math without touching RNG: `_perio_stage_weights` (the report averages these vectors for the model-expected stage mix) and `_perio_risk_tier` (called by both `_perio_recall_days` and the snapshot). Keep the pure halves RNG-free.
- Fidelity tolerances are **sampling-noise-aware** (`stol()` = ~4 SE of a proportion) so the gate is robust across seeds; distribution/trajectory metrics auto-ungate under a `--stage`/`--grade` lock.

**Medical-history layer (`_generate_medical_history`, `--no-medical`).** Emits the six Open Dental medical tables (`diseasedef`/`disease`, `medication`/`medicationpat`, `allergydef`/`allergy`) for adults, plus three contact-preference columns on `patient`. Driven by `DISEASE_CATALOG` / `MEDICATION_CATALOG` / `ALLERGY_CATALOG`. Key rules:

- **Runs LAST in `generate_all` (after `_generate_payments`), on purpose.** It draws its own RNG after every other module's draws, so toggling it — or editing its catalog — never shifts the bytes of any table above it; only the appended rows change. This is what makes it a clean, additive layer (verified by a HEAD-vs-new same-seed diff: only the `patient` columns + appended medical tables differ). Adding a `random`/`Faker` draw *inside* an earlier module would desync everything downstream — don't.
- **Diabetes and tobacco reuse the perio latents** (`patient["perio"]["diabetic"]`/`["smoker"]`) — never re-drawn — so the systemic↔periodontal coupling is exact. Because it reads `patient["perio"]`, the layer requires the perio module and is skipped under `--no-perio`.
- **Contact prefs (`PreferContactMethod` etc.) are RNG-free pure functions** of fields already drawn in `_create_patient` (`TxtMsgOk`, `Email`, `WirelessPhone`, `Age`). Never insert a `random.*` call among the existing patient draws — it would shift the stream for every later patient and table.
- **Truth vs documentation.** Each adult's true conditions/meds/allergies are drawn first, then *documented* with sub-1.0 sensitivity (`doc_sens` per condition, `MED_DOC_SENSITIVITY`, `ALLERGY_DOC_SENSITIVITY`) so `labels.json` can score a screening query's recall/precision. `documented ⊆ true` is a hard invariant (`check_medical.py`).
- **Catalog edits**: a `DISEASE_CATALOG` entry needs a real ICD-10 + SNOMED (verify against tx.fhir.org), a prevalence lambda `(age, female, perio, truth)`, a `doc_sens`, and meds referencing `MEDICATION_CATALOG` keys; a new med needs a real RxNorm ingredient RxCui (verify via RxNav). Entries whose lambda reads `truth` must come *after* the entries they depend on (the catalog is drawn in order). Keep the README prevalence/characteristics list and the fidelity gated set in sync.

**Study-eligibility answer key (`_evaluate_eligibility`, `study_eligibility` in labels).** The dataset is scored against a real protocol — Biolectrics **OraFlow-US-003** (adults, Periodontitis Stage I–III Grade A/B, ≥8 BOP+PD≥4mm sites, decline SRP). `_evaluate_eligibility` is a **pure** function (no RNG) run in `_finalize_perio_labels` that judges all 9 inclusion + 19 exclusion criteria against ground truth and emits `study_eligibility` per adult. Rules:

- It reads only latent truth (perio profile, `patient["medical"]`), the exam snapshots, and `self.procedures` — never RNG. `eligible` = every *evaluable* inclusion met AND no evaluable exclusion triggered; consent/behavioral/unmodeled criteria are listed in `not_evaluable`.
- The enrollment gate IC3 / primary endpoint is `qualifying_site_count` = **current-exam** sites with **BOP AND PD≥4mm** — assessed on the patient's *most recent* chart (`exams[-1]`), since screening measures current status, not their earliest historical chart. That needs per-site BOP, so `_emit_perio_exam` captures `teeth[t]["bop"]` in the snapshot (a pure reuse of the already-drawn bleeding value — do not add a draw) and `max_mobility` for EX5. `check_eligibility.py` recomputes IC3/IC5 membership from that same current exam.
- The `eligible_cohort_prevalence` fidelity metric **ungates under a `--stage`/`--grade` lock** (Stage IV / Grade C legitimately yield 0 eligible), mirroring the trajectory/progression metrics. Checkers read the generator's frozen day from `labels.meta.generated_date` (never `date.today()`) so re-verifying a saved pair can't false-fail on date-window criteria.
- IC4 "declined SRP" is a **treatment-planned (ProcStatus=1) D4341/D4342 with no completion**, emitted by `_generate_study_signals` (tail pass, appended procedurelog rows — byte-stable). **QA checkers that identify "treated" patients must filter `ProcStatus==2`** or the declined pool pollutes them (already fixed in `qa_validate.py`/`qa_flags.py`).
- Controlled/uncontrolled status (only *uncontrolled* trips EX10) is a latent flag → `disease.PatNote="Uncontrolled"` + labels; `UNCONTROLLED_PROB` governs it. Protocol-signal med/condition sets (`ANTICOAGULANT_MEDS`, `ANTIBIOTIC_MEDS`, `PREMED_CONDITIONS`, `GINGIVAL_HYPERPLASIA_MEDS`, …) live next to the catalogs — keep the evaluator and these in sync.
- `tests/check_eligibility.py` proves the key describes the SQL (recomputes `qualifying_site_count` from `periomeasure`); `tests/score_eligibility.py` demonstrates a naive query's recall/precision vs the key. `labels.meta.schema_version` is **3**.

## Domain rules to preserve

- **Real ADA code mapping is mandatory.** A procedure code is only emitted if it exists in BOTH `PROCEDURE_CODES` (definition + fee range + category) AND `REAL_CODE_TO_CODENUM` (ADA code → real OD `CodeNum`). `__init__` silently drops any `PROCEDURE_CODES` entry with no `CodeNum` mapping. To add a code, edit both structures.
- **`*_DEFNUMS` constants** (`BILLING_TYPE_DEFNUMS`, `PAYMENT_TYPE_DEFNUMS`, `PROC_CAT_DEFNUMS`) are real `definition.DefNum` values from Open Dental — don't invent them.
- **Statistical targets are intentional**, tuned by probabilities scattered through the generators: ~94% solo vs family patients (`_generate_patients`), ~53% insured, ~76% with treatment-planned procedures, ~26% overdue for hygiene, ~20% with a future appointment, plus a US dental `AGE_DISTRIBUTION`. Changing a magic probability shifts a documented characteristic in the README — keep them in sync.
- **Families share a guarantor**: the head of household is its own guarantor (`Guarantor == PatNum`); members point at the head's `PatNum`, and insurance subscribers usually resolve to the guarantor.
- **Metro areas**: `METRO_AREAS` carries real ZIP codes for 10 cities. An unrecognized `--city/--state` synthesizes 20 random ZIPs instead.
