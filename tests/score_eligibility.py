#!/usr/bin/env python3
"""Demonstration: score a naive SQL recruitment query against the OraFlow-US-003 answer key.

Usage:  python tests/score_eligibility.py <generated.sql> <labels.json>

This is the point of the whole eligibility benchmark. A recruitment coordinator's screening
query can only see the *documented* EHR (the SQL). The labels carry ground truth. Running a
realistic-but-naive query here and scoring it against the answer key shows the recall and
precision a real patient-mining tool would achieve -- and *why* it misses: incomplete problem
lists let ineligible patients (undocumented tobacco, uncontrolled disease, ...) slip through.

The query below screens on the criteria a simple structured query can express (age, the
BOP+PD>=4 site count, a standing treatment-planned SRP, tooth count; excluding documented
tobacco / anticoagulants / recent SRP-prophy / pregnancy). It deliberately does NOT catch the
criteria a naive query misses (uncontrolled disease in a free-text note, premed conditions,
recent antibiotics, hyperplasia meds, mobility) -- exactly where precision leaks.

Exit status is always 0 (informational); it only errors if the eligible cohort is empty.
"""
import json, os, sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa_validate import parse

SITE = ["MBvalue", "Bvalue", "DBvalue", "MLvalue", "Lvalue", "DLvalue"]
ANTICOAG_RXCUI = {11289, 1364430, 1114195, 32968}   # warfarin, apixaban, rivaroxaban, clopidogrel


def main():
    rows = parse(sys.argv[1])
    doc = json.load(open(sys.argv[2]))
    # Use the generator's frozen day (from labels meta), not the checker's calendar day, so
    # the date-window filters score identically regardless of when this is run.
    today = datetime.strptime(doc["meta"]["generated_date"][:10], "%Y-%m-%d").date()

    patients = {p["PatNum"]: p for p in rows["patient"]}
    proccodes = {pc["CodeNum"]: pc["ProcCode"] for pc in rows["procedurecode"]}
    ddef = {d["DiseaseDefNum"]: d for d in rows.get("diseasedef", [])}

    # current (most recent) exam + per-site probing/bleeding -- a real screening query
    # reads the patient's latest chart, matching how the answer key assesses IC3.
    exams_by_pat = {}
    for e in rows["perioexam"]:
        exams_by_pat.setdefault(e["PatNum"], []).append(e)
    baseline = {pn: max(es, key=lambda e: (e["ExamDate"], e["PerioExamNum"]))["PerioExamNum"]
                for pn, es in exams_by_pat.items()}
    probing, bleeding, exam_teeth = {}, {}, {}
    for m in rows["periomeasure"]:
        k = (m["PerioExamNum"], m["IntTooth"])
        if m["SequenceType"] == 4:
            probing[k] = [m[c] for c in SITE]; exam_teeth.setdefault(m["PerioExamNum"], set()).add(m["IntTooth"])
        elif m["SequenceType"] == 6:
            bleeding[k] = [m[c] for c in SITE]

    def age(pn):
        return (today - datetime.strptime(patients[pn]["Birthdate"], "%Y-%m-%d").date()).days // 365
    def days_ago(s):
        return (today - datetime.strptime(s[:10], "%Y-%m-%d").date()).days

    procs_by_pat = {}
    for p in rows["procedurelog"]:
        p["ProcCode"] = proccodes.get(p["CodeNum"])
        procs_by_pat.setdefault(p["PatNum"], []).append(p)
    # documented disease/med lookups
    tobacco_defs = {n for n, d in ddef.items() if d["Icd10Code"] == "F17.210"}
    preg_defs = {n for n, d in ddef.items() if d["Icd10Code"] == "Z33.1"}
    dz_by_pat = {}
    for dz in rows.get("disease", []):
        dz_by_pat.setdefault(dz["PatNum"], set()).add(dz["DiseaseDefNum"])
    anticoag_pat = {m["PatNum"] for m in rows.get("medicationpat", []) if m["RxCui"] in ANTICOAG_RXCUI}

    # --- the naive screening query (SQL-visible signals only) ---
    candidates = set()
    for pn in patients:
        en = baseline.get(pn)
        if en is None:
            continue
        if not (22 <= age(pn) <= 75):
            continue
        teeth = exam_teeth.get(en, set())
        if len(teeth) < 18:
            continue
        q = sum(1 for t in teeth for i in range(6)
                if probing.get((en, t), [0]*6)[i] >= 4 and (bleeding.get((en, t), [0]*6)[i] & 1))
        if q < 8:
            continue
        procs = procs_by_pat.get(pn, [])
        if not any(p["ProcCode"] in ("D4341", "D4342") and p["ProcStatus"] == 1 for p in procs):
            continue        # IC4: standing treatment-planned SRP
        # documented exclusions the naive query can express
        if dz_by_pat.get(pn, set()) & (tobacco_defs | preg_defs):
            continue
        if pn in anticoag_pat:
            continue
        if any(p["ProcStatus"] == 2 and (
                (p["ProcCode"] in ("D4341", "D4342") and 0 <= days_ago(p["ProcDate"]) <= 91) or
                (p["ProcCode"] in ("D4260", "D4261") and 0 <= days_ago(p["ProcDate"]) <= 182) or
                (p["ProcCode"] == "D1110" and 0 <= days_ago(p["ProcDate"]) <= 91)) for p in procs):
            continue
        candidates.add(pn)

    # --- score against the answer key ---
    truth = {r["PatNum"]: r["study_eligibility"] for r in doc["patients"] if "study_eligibility" in r}
    eligible = {pn for pn, se in truth.items() if se["eligible"]}
    tp = candidates & eligible
    recall = len(tp) / len(eligible) if eligible else float("nan")
    precision = len(tp) / len(candidates) if candidates else float("nan")

    print(f"\n=== OraFlow-US-003 naive-query scoring ({os.path.basename(sys.argv[1])}) ===")
    print(f"  truly eligible (answer key): {len(eligible)}")
    print(f"  query candidates:            {len(candidates)}")
    print(f"  correct (true positives):    {len(tp)}")
    print(f"  recall    = {recall:.3f}   (fraction of eligible subjects the query found)")
    print(f"  precision = {precision:.3f}   (fraction of candidates who are truly eligible)")

    # why the false positives leak through -- what the naive query missed
    fp = candidates - eligible
    reasons = {}
    for pn in fp:
        se = truth.get(pn)
        if not se:
            continue
        for k in se["triggered_exclusion"] + se["failed_inclusion"]:
            reasons[k] = reasons.get(k, 0) + 1
    if fp:
        print(f"\n  {len(fp)} false positives -- criteria the naive query could not see:")
        for k, c in sorted(reasons.items(), key=lambda kv: -kv[1]):
            print(f"    {k:<26} {c}")
    print("\n  Takeaway: incomplete problem lists inflate the candidate pool; the answer key\n"
          "  quantifies exactly which criteria a smarter query must recover.")

    if not eligible:
        print("ERROR: empty eligible cohort")
        sys.exit(1)


if __name__ == "__main__":
    main()
