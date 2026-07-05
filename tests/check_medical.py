#!/usr/bin/env python3
"""Integrity check for the structured medical-history layer (problem list, medications,
allergies) against the emitted SQL and the ground-truth labels.

Usage:  python tests/check_medical.py <generated.sql> <labels.json>

Proves the medical tables are a trustworthy recruitment benchmark:
  1. FK integrity + adults-only + def-table completeness/uniqueness,
  2. every documented row traces back to a TRUE item in the labels (documented is a
     subset of truth -- the whole point of the documentation-gap model), and
  3. clinical coherence (pregnancy => female 18-45, tobacco/diabetes tie to the perio
     latents, bisphosphonate => osteoporosis, ProbStatus/DateStop consistency, RxCui
     sync between medicationpat and medication, dates not in the future).
"""
import json, os, sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa_validate import parse

MINDATE = "0001-01-01"

failures = []
def check(cond, msg):
    print(("  PASS: " if cond else "  FAIL: ") + msg)
    if not cond:
        failures.append(msg)


def as_date(s):
    """Parse an emitted SQL date; MySQL min-date sentinels count as 'unset' (None)."""
    if not s or s.startswith("0001-01-01") or s.startswith("0000"):
        return None
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def main():
    if len(sys.argv) != 3:
        print("usage: check_medical.py <generated.sql> <labels.json>")
        sys.exit(2)
    sqlpath, labpath = sys.argv[1], sys.argv[2]
    rows = parse(sqlpath)
    with open(labpath) as f:
        doc = json.load(f)
    # Generator's frozen day (from labels), not the checker's calendar day, so re-verifying
    # a saved pair stays reproducible -- consistent with check_eligibility/score_eligibility.
    today = datetime.strptime(doc["meta"]["generated_date"][:10], "%Y-%m-%d").date()
    print(f"\n=== Medical-history integrity: {os.path.basename(sqlpath)} ===")
    check(not rows.get("_PARSE_ERROR"), "SQL parses cleanly")

    diseasedefs = {d["DiseaseDefNum"]: d for d in rows.get("diseasedef", [])}
    medications = {m["MedicationNum"]: m for m in rows.get("medication", [])}
    allergydefs = {a["AllergyDefNum"]: a for a in rows.get("allergydef", [])}
    diseases = rows.get("disease", [])
    medicationpats = rows.get("medicationpat", [])
    allergies = rows.get("allergy", [])
    patients = {p["PatNum"]: p for p in rows["patient"]}

    print(f"  ({len(diseasedefs)} diseasedefs, {len(diseases)} diseases, "
          f"{len(medications)} medications, {len(medicationpats)} medicationpats, "
          f"{len(allergydefs)} allergydefs, {len(allergies)} allergies)")

    check(diseases and medicationpats and allergies, "medical tables are non-empty")

    # --- def tables: complete + unique ---
    check(len(diseasedefs) == len(rows.get("diseasedef", [])), "DiseaseDefNum values unique")
    check(len(medications) == len(rows.get("medication", [])), "MedicationNum values unique")
    check(len(allergydefs) == len(rows.get("allergydef", [])), "AllergyDefNum values unique")
    icd10s = [d["Icd10Code"] for d in diseasedefs.values()]
    check(len(icd10s) == len(set(icd10s)), "diseasedef ICD-10 codes unique")
    check(all(d["SnomedCode"] for d in diseasedefs.values()), "every diseasedef has a SNOMED code")
    rxcuis = [m["RxCui"] for m in medications.values()]
    check(len(rxcuis) == len(set(rxcuis)), "medication RxCui values unique")
    check(all(m["GenericNum"] == m["MedicationNum"] for m in medications.values()),
          "every medication.GenericNum self-references (generic)")

    # --- FK integrity ---
    check(all(d["DiseaseDefNum"] in diseasedefs for d in diseases),
          "every disease.DiseaseDefNum resolves")
    check(all(m["MedicationNum"] in medications for m in medicationpats),
          "every medicationpat.MedicationNum resolves")
    check(all(a["AllergyDefNum"] in allergydefs for a in allergies),
          "every allergy.AllergyDefNum resolves")
    check(all(d["PatNum"] in patients for d in diseases)
          and all(m["PatNum"] in patients for m in medicationpats)
          and all(a["PatNum"] in patients for a in allergies),
          "every medical PatNum exists in the patient table")

    # --- RxCui sync: medicationpat must carry its def's RxCui ---
    rx_bad = sum(1 for m in medicationpats if m["RxCui"] != medications[m["MedicationNum"]]["RxCui"])
    check(rx_bad == 0, f"medicationpat.RxCui matches its medication def ({rx_bad} mismatches)")

    # --- adults only ---
    def age(pn):
        bd = datetime.strptime(patients[pn]["Birthdate"], "%Y-%m-%d").date()
        return (today - bd).days // 365
    med_pats = {d["PatNum"] for d in diseases} | {m["PatNum"] for m in medicationpats} \
        | {a["PatNum"] for a in allergies}
    minors = [pn for pn in med_pats if age(pn) < 18]
    check(not minors, f"no medical rows for minors ({len(minors)} minors with medical data)")

    # --- ProbStatus / date consistency ---
    active_bad = sum(1 for d in diseases if d["ProbStatus"] == 0 and as_date(d["DateStop"]))
    check(active_bad == 0, f"active problems (ProbStatus=0) have no DateStop ({active_bad} bad)")
    future = sum(1 for d in diseases if (as_date(d["DateStart"]) or today) > today)
    check(future == 0, f"no disease DateStart in the future ({future} bad)")
    mp_future = sum(1 for m in medicationpats if (as_date(m["DateStart"]) or today) > today)
    check(mp_future == 0, f"no medicationpat DateStart in the future ({mp_future} bad)")

    # --- truth join: documented is a subset of true (per patient) ---
    lab = {p["PatNum"]: p for p in doc["patients"]}
    check(doc["meta"]["schema_version"] == 3, "labels schema_version == 3")

    # Map def nums back to catalog keys via the label join keys.
    dis_key = {}   # DiseaseNum -> condition key
    med_key = {}   # MedicationPatNum -> med key
    for p in doc["patients"]:
        m = p.get("medical")
        if not m:
            continue
        for d in m["documented_conditions"]:
            dis_key[d["DiseaseNum"]] = d["key"]
        for md in m["documented_medications"]:
            med_key[md["MedicationPatNum"]] = md["key"]
        for md in m.get("recent_medications", []):   # antibiotics / rinses / hyperplasia drugs
            med_key[md["MedicationPatNum"]] = md["key"]

    # Every emitted disease/medicationpat row appears in some patient's documented set.
    dis_join = sum(1 for d in diseases if d["DiseaseNum"] not in dis_key)
    check(dis_join == 0, f"every SQL disease row is represented in labels ({dis_join} orphans)")
    med_join = sum(1 for m in medicationpats if m["MedicationPatNum"] not in med_key)
    check(med_join == 0, f"every SQL medicationpat row is represented in labels ({med_join} orphans)")

    # CONTENT check: a disease row's actual code (its DiseaseDefNum -> diseasedef.Icd10Code)
    # must match the ICD-10 the label claims for that DiseaseNum. Catches a scrambled/
    # mislabelled condition-code assignment that FK-resolution alone would miss.
    sql_disease = {d["DiseaseNum"]: d for d in diseases}
    lbl_icd10 = {}
    for p in doc["patients"]:
        for dc in p.get("medical", {}).get("documented_conditions", []):
            lbl_icd10[dc["DiseaseNum"]] = dc["icd10"]
    content_bad = 0
    for dnum, icd in lbl_icd10.items():
        d = sql_disease.get(dnum)
        dd = diseasedefs.get(d["DiseaseDefNum"]) if d else None
        if not dd or dd["Icd10Code"] != icd:
            content_bad += 1
    check(content_bad == 0, f"disease row code (SQL Icd10Code) matches the labelled condition ({content_bad} bad)")

    # recent_medications (antibiotics / rinses / hyperplasia drugs) key sanity.
    INDEP_KEYS = {"amoxicillin", "doxycycline", "azithromycin", "metronidazole", "clindamycin",
                  "chlorhexidine_rinse", "cpc_rinse", "phenytoin", "cyclosporine"}
    recent_bad = sum(1 for p in doc["patients"]
                     for rm in p.get("medical", {}).get("recent_medications", [])
                     if rm["key"] not in INDEP_KEYS)
    check(recent_bad == 0, f"recent_medications keys are known independent drugs ({recent_bad} bad)")

    # documented condition/med/allergy keys are a subset of the patient's TRUE keys.
    sub_bad = 0
    for p in doc["patients"]:
        m = p.get("medical")
        if not m:
            continue
        true_c = {t["key"] for t in m["true_conditions"]}
        true_m = {t["key"] for t in m["true_medications"]}
        true_a = set(m["true_allergies"])
        if any(d["key"] not in true_c for d in m["documented_conditions"]):
            sub_bad += 1
        if any(md["key"] not in true_m for md in m["documented_medications"]):
            sub_bad += 1
        if any(a["key"] not in true_a for a in m["documented_allergies"]):
            sub_bad += 1
    check(sub_bad == 0, f"documented conditions/meds/allergies are subsets of truth ({sub_bad} violations)")

    # --- clinical coherence (against labelled truth) ---
    def true_keys(p):
        return {t["key"] for t in p["medical"]["true_conditions"]} if p.get("medical") else set()

    preg_bad = 0
    tob_bad = dm_bad = 0
    copd_bad = 0
    bis_bad = 0
    mtx_bad = 0
    antico_bad = 0
    excl_bad = 0
    pcn_amox_bad = 0
    ANTICO = {"apixaban", "warfarin", "rivaroxaban"}
    for p in doc["patients"]:
        m = p.get("medical")
        if not m:
            continue
        tk = true_keys(p)
        tm = {t["key"] for t in m["true_medications"]}
        female, a = p["gender"] == 1, p["age"]
        if "pregnancy" in tk and not (female and 18 <= a <= 45):
            preg_bad += 1
        # tobacco truth must equal the smoker latent; diabetes truth must cover diabetics
        if ("tobacco" in tk) != bool(p["profile"]["smoker"]):
            tob_bad += 1
        if p["profile"]["diabetic"] and not ({"t2dm", "t1dm"} & tk):
            dm_bad += 1
        if "copd" in tk and not (p["profile"]["smoker"] or "former_smoker" in tk):
            copd_bad += 1
        # current + former smoker are mutually exclusive
        if "tobacco" in tk and "former_smoker" in tk:
            excl_bad += 1
        # drug -> indication (truth level)
        if "alendronate" in tm and "osteoporosis" not in tk:
            bis_bad += 1
        if "methotrexate" in tm and "ra" not in tk:
            mtx_bad += 1
        if (ANTICO & tm) and "afib" not in tk:
            antico_bad += 1
        # Allergy-aware prescribing: a penicillin/amoxicillin-allergic patient must not
        # have been dispensed amoxicillin (a penicillin).
        recent_keys = {x["key"] for x in m.get("recent_medications", [])}
        if "amoxicillin" in recent_keys and ({"penicillin", "amoxicillin"} & set(m.get("true_allergies", []))):
            pcn_amox_bad += 1
    check(preg_bad == 0, f"pregnancy only in females 18-45 ({preg_bad} bad)")
    check(tob_bad == 0, f"tobacco truth matches the smoker latent ({tob_bad} bad)")
    check(dm_bad == 0, f"every diabetic latent has a true diabetes condition ({dm_bad} bad)")
    check(copd_bad == 0, f"COPD only in ever-smokers ({copd_bad} bad)")
    check(excl_bad == 0, f"no patient is both current and former smoker ({excl_bad} bad)")
    check(bis_bad == 0, f"bisphosphonate only with osteoporosis ({bis_bad} bad)")
    check(mtx_bad == 0, f"methotrexate only with rheumatoid arthritis ({mtx_bad} bad)")
    check(antico_bad == 0, f"anticoagulant only with atrial fibrillation ({antico_bad} bad)")
    check(pcn_amox_bad == 0, f"no amoxicillin dispensed to a penicillin/amoxicillin-allergic patient ({pcn_amox_bad} bad)")

    # Uncontrolled free-text note only on controllable conditions (diabetes/HTN/cancer).
    CONTROLLABLE_ICD10 = {"E11.9", "E10.9", "I10", "C80.1"}
    unctrl_bad = 0
    for d in diseases:
        if isinstance(d.get("PatNote"), str) and "Uncontrolled" in d["PatNote"]:
            dd = diseasedefs.get(d["DiseaseDefNum"])
            if not dd or dd["Icd10Code"] not in CONTROLLABLE_ICD10:
                unctrl_bad += 1
    check(unctrl_bad == 0, f"'Uncontrolled' note only on diabetes/HTN/cancer problems ({unctrl_bad} bad)")

    print(f"\n{'PASS' if not failures else 'FAIL'}: "
          f"{len(failures)} failing check(s)" if failures else "\nAll medical-history checks passed.")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
