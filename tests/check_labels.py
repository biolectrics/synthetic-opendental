#!/usr/bin/env python3
"""Integrity check: the ground-truth labels JSON provably describes the emitted SQL.

Usage:  python tests/check_labels.py <generated.sql> <labels.json>

Proves the two claims that make the labels a trustworthy benchmark answer key:
  1. the emitted probing in the SQL is EXACTLY the labels' observed_pd_mm, and
  2. the stored CAL (probing + gingival margin) is the labels' noise-free true CAL rounded
     to the nearest mm -- i.e. the labeled measurement error is real and self-consistent.
Also checks structure: minors absent, uncharted patients represented, join coverage, and
(default mode) that each patient's baseline stage matches the labeled true stage.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa_validate import parse

SITE = ["MBvalue", "Bvalue", "DBvalue", "MLvalue", "Lvalue", "DLvalue"]
COLLAPSE = {"healthy": "healthy", "I": "I", "II": "II", "III": "severe", "IV": "severe"}

failures = []
def check(cond, msg):
    print(("  PASS: " if cond else "  FAIL: ") + msg)
    if not cond:
        failures.append(msg)


def decode_ging(g):
    """GingMargin: a coronal (negative) margin is stored as 100+|v|."""
    return (100 - g) if g >= 100 else g


def main():
    if len(sys.argv) != 3:
        print("usage: check_labels.py <generated.sql> <labels.json>")
        sys.exit(2)
    sqlpath, labpath = sys.argv[1], sys.argv[2]
    rows = parse(sqlpath)
    with open(labpath) as f:
        doc = json.load(f)
    pats = doc["patients"]
    print(f"\n=== Labels integrity: {os.path.basename(labpath)} vs {os.path.basename(sqlpath)} ===")
    check(not rows.get("_PARSE_ERROR"), "SQL parses cleanly")
    check(doc.get("meta", {}).get("schema_version") == 3, "labels meta.schema_version == 3")

    # SQL per-site lookups keyed on (PerioExamNum, IntTooth)
    probing, ging = {}, {}
    for m in rows["periomeasure"]:
        key = (m["PerioExamNum"], m["IntTooth"])
        if m["SequenceType"] == 4:
            probing[key] = [m[c] for c in SITE]
        elif m["SequenceType"] == 2:
            ging[key] = [m[c] for c in SITE]
    sql_patnums = {p["PatNum"] for p in rows["patient"]}
    sql_exam_pat = {e["PerioExamNum"]: e["PatNum"] for e in rows["perioexam"]}

    # --- population structure ---
    check(all(r["age"] >= 18 for r in pats), "no minors in labels (all age >= 18)")
    check(all(r["PatNum"] in sql_patnums for r in pats), "every labels PatNum exists in the SQL patient table")
    charted = [r for r in pats if r["charted"]]
    uncharted = [r for r in pats if not r["charted"]]
    check(len(charted) > 0 and all(r["exams"] for r in charted), "charted patients each have >= 1 exam")
    check(all(not r["exams"] and r["trajectory"] is None for r in uncharted),
          f"uncharted patients ({len(uncharted)}) have no exams and null trajectory")
    lab_patnums = {r["PatNum"] for r in pats}
    check(all(pn in lab_patnums for pn in sql_exam_pat.values()),
          "every SQL perioexam belongs to a labeled patient")

    # --- the two integrity claims, over every charted site ---
    n_sites = miss = pd_mismatch = cal_mismatch = 0
    for r in charted:
        for e in r["exams"]:
            en = e["PerioExamNum"]
            for tooth, td in e["teeth"].items():
                key = (en, int(tooth))
                sql_pd = probing.get(key)
                sql_g = ging.get(key)
                if sql_pd is None or sql_g is None:
                    miss += 1
                    continue
                for i in range(6):
                    n_sites += 1
                    if td["observed_pd_mm"][i] != sql_pd[i]:
                        pd_mismatch += 1
                    sql_cal = sql_pd[i] + decode_ging(sql_g[i])       # Open Dental CAL
                    if abs(sql_cal - td["true_cal_mm"][i]) > 0.5 + 1e-9:
                        cal_mismatch += 1
    check(miss == 0, f"every labeled exam/tooth joins to a SQL probing+margin row ({miss} misses)")
    check(n_sites > 0 and pd_mismatch == 0,
          f"labels observed_pd_mm == SQL probing at all {n_sites} sites ({pd_mismatch} mismatches)")
    check(cal_mismatch == 0,
          f"SQL CAL (probing+margin) == round(true CAL) within 0.5mm at all {n_sites} sites ({cal_mismatch} off)")

    # --- baseline stage consistency (default mode only) ---
    if not doc["meta"]["flags"]["stage_lock"]:
        perio = [r for r in charted if r["profile"]["true_stage"] != "healthy"]
        ok = sum(1 for r in perio
                 if COLLAPSE[r["exams"][0]["stage_at_visit"]] == COLLAPSE[r["profile"]["true_stage"]])
        frac = ok / max(1, len(perio))
        check(frac >= 0.85,
              f"baseline stage_at_visit matches labeled true_stage for >=85% of perio patients ({100*frac:.0f}%, n={len(perio)})")

    # --- trajectory / response label sanity ---
    treated = [r for r in charted if r["profile"]["treated"] and r["trajectory"]]
    if treated:
        resp = {r["trajectory"]["treatment_response"] for r in treated}
        check(resp <= {"responder", "partial", "refractory", "unknown"},
              f"treatment_response values are valid ({sorted(resp)})")
    classes = {r["trajectory"]["class"] for r in charted if r["trajectory"]}
    check(classes <= {"stable", "downhill", "extreme"}, f"trajectory classes valid ({sorted(classes)})")

    print(f"\n{len(failures)} FAILURE(S)" if failures else "\nALL LABELS INTEGRITY CHECKS PASSED")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
