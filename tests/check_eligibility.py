#!/usr/bin/env python3
"""Integrity check for the OraFlow-US-003 study-eligibility answer key in labels.json.

Usage:  python tests/check_eligibility.py <generated.sql> <labels.json>

Proves the answer key describes the SQL and is internally consistent:
  1. qualifying_site_count (the IC3 enrollment gate / primary-endpoint basis) recomputed
     independently from the SQL periomeasure rows -- probing (SequenceType 4) >=4 mm AND
     bleeding-on-probing (SequenceType 6, bleed bit) at the SAME site, in the CURRENT
     (most recent) exam -- equals the labelled count, and the IC3 membership is derived
     from that recount (not the label's own list) so a mispopulated flag is caught.
  2. natural_teeth + per-quadrant (IC5), the mobility exclusion (EX5), and the
     procedure-based criteria (IC4 declined-SRP, EX1 recent SRP/surgery, EX2 recent prophy)
     match the SQL directly; IC1/IC3/IC5 memberships are cross-checked, not assumed.
  3. Every evaluable exclusion (EX6/EX7/EX9-EX16) is independently re-derived from the
     labelled ground truth (profile + medical truth) and matched to the answer key.
Date windows use the GENERATOR's day (labels meta.generated_date), so re-verifying a
saved sql+labels pair on a later day does not false-fail.
"""
import json, os, sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa_validate import parse

SITE = ["MBvalue", "Bvalue", "DBvalue", "MLvalue", "Lvalue", "DLvalue"]
SEQ_MOBILITY, SEQ_PROBING, SEQ_BLEEDING = 0, 4, 6
BLEED_BIT = 1

failures = []
def check(cond, msg):
    print(("  PASS: " if cond else "  FAIL: ") + msg)
    if not cond:
        failures.append(msg)


def tooth_quadrant(t):
    return "UR" if t <= 8 else "UL" if t <= 16 else "LL" if t <= 24 else "LR"


def main():
    if len(sys.argv) != 3:
        print("usage: check_eligibility.py <generated.sql> <labels.json>")
        sys.exit(2)
    rows = parse(sys.argv[1])
    doc = json.load(open(sys.argv[2]))
    # Use the GENERATOR's day (frozen in the labels), NOT the checker's calendar day, so
    # the date-window criteria (EX1/EX2/EX13) verify identically no matter when the check
    # runs -- otherwise re-verifying a saved sql+labels pair on a later day false-fails.
    today = datetime.strptime(doc["meta"]["generated_date"][:10], "%Y-%m-%d").date()
    print(f"\n=== Study-eligibility integrity: {os.path.basename(sys.argv[1])} ===")
    check(not rows.get("_PARSE_ERROR"), "SQL parses cleanly")
    check(doc["meta"]["schema_version"] == 3, "labels schema_version == 3")

    # --- index the SQL ---
    # most-recent exam per patient = the screening/current chart (matches the generator,
    # which assesses IC3/IC5/EX5 on the patient's current status, not their earliest chart)
    exams_by_pat = {}
    for e in rows["perioexam"]:
        exams_by_pat.setdefault(e["PatNum"], []).append(e)
    current = {pn: max(es, key=lambda e: (e["ExamDate"], e["PerioExamNum"]))["PerioExamNum"]
               for pn, es in exams_by_pat.items()}
    # per-exam, per-tooth probing / bleeding / mobility
    probing, bleeding, mobility = {}, {}, {}
    for m in rows["periomeasure"]:
        key = (m["PerioExamNum"], m["IntTooth"])
        if m["SequenceType"] == SEQ_PROBING:
            probing[key] = [m[c] for c in SITE]
        elif m["SequenceType"] == SEQ_BLEEDING:
            bleeding[key] = [m[c] for c in SITE]
        elif m["SequenceType"] == SEQ_MOBILITY:
            mobility[key] = m["ToothValue"]
    exam_teeth = {}
    for (en, tooth) in probing:
        exam_teeth.setdefault(en, set()).add(tooth)

    proccodes = {pc["CodeNum"]: pc["ProcCode"] for pc in rows["procedurecode"]}
    procs_by_pat = {}
    for p in rows["procedurelog"]:
        p["ProcCode"] = proccodes.get(p["CodeNum"])
        procs_by_pat.setdefault(p["PatNum"], []).append(p)

    def days_ago(s):
        return (today - datetime.strptime(s[:10], "%Y-%m-%d").date()).days

    # --- per-patient verification ---
    site_mismatch = teeth_mismatch = mob_mismatch = 0
    ic1_mismatch = ic2_mismatch = ic3_mismatch = ic5_mismatch = 0
    ic4_mismatch = ex1_mismatch = ex2_mismatch = 0
    elig_mismatch = truth_ex_mismatch = 0
    checked = 0
    for r in doc["patients"]:
        se = r.get("study_eligibility")
        if not se:
            continue
        pn = r["PatNum"]
        fi, te = se["failed_inclusion"], se["triggered_exclusion"]
        checked += 1
        # Uncharted patients (en is None) fall through with an empty exam: exam_teeth.get(
        # None) -> (), so q=0 / teeth=empty and IC3/IC5 correctly fail -- but IC1, the
        # procedure-based criteria, the eligible flag, and every truth-based exclusion are
        # STILL verified (they apply regardless of charting).
        en = current.get(pn)
        # (1) qualifying_site_count recomputed from SQL, and the IC3 membership derived
        # from it (not from the label's own list) -- so a mispopulated IC3 flag is caught.
        q = 0
        for tooth in exam_teeth.get(en, ()):
            pdv = probing.get((en, tooth), [0] * 6)
            blv = bleeding.get((en, tooth), [0] * 6)
            for i in range(6):
                if pdv[i] >= 4 and (blv[i] & BLEED_BIT):
                    q += 1
        if q != se["qualifying_site_count"]:
            site_mismatch += 1
        if (q < 8) != ("IC3_sites" in fi):
            ic3_mismatch += 1
        # (2) natural_teeth + per-quadrant recomputed from SQL, IC5 membership derived
        teeth = exam_teeth.get(en, set())
        if len(teeth) != se["natural_teeth"]:
            teeth_mismatch += 1
        quad = {}
        for t in teeth:
            quad[tooth_quadrant(t)] = quad.get(tooth_quadrant(t), 0) + 1
        ic5_fail = len(teeth) < 18 or any(quad.get(qd, 0) < 2 for qd in ("UR", "UL", "LL", "LR"))
        if ic5_fail != ("IC5_teeth" in fi):
            ic5_mismatch += 1
        # (1b) IC1 age + IC2 stage/grade membership vs the labelled truth
        if (not (22 <= r["age"] <= 75)) != ("IC1_age" in fi):
            ic1_mismatch += 1
        ic2_fail = not (r["profile"]["true_stage"] in ("I", "II", "III")
                        and r["profile"]["true_grade"] in ("A", "B"))
        if ic2_fail != ("IC2_stage_grade" in fi):
            ic2_mismatch += 1
        # (2) EX5 mobility>2 from SQL
        sql_maxmob = max((mobility.get((en, t), 0) for t in teeth), default=0)
        if (sql_maxmob > 2) != ("EX5_mobility" in te):
            mob_mismatch += 1
        # (2) procedure-based criteria from SQL
        procs = procs_by_pat.get(pn, [])
        has_tp_srp = any(p["ProcCode"] in ("D4341", "D4342") and p["ProcStatus"] == 1 for p in procs)
        if has_tp_srp == ("IC4_declined_srp" in fi):
            ic4_mismatch += 1        # has TP SRP <=> IC4 NOT failed
        recent_srp_surg = any(
            ((p["ProcCode"] in ("D4341", "D4342") and 0 <= days_ago(p["ProcDate"]) <= 91) or
             (p["ProcCode"] in ("D4260", "D4261") and 0 <= days_ago(p["ProcDate"]) <= 182))
            and p["ProcStatus"] == 2 for p in procs)
        if recent_srp_surg != ("EX1_recent_srp_surgery" in te):
            ex1_mismatch += 1
        recent_prophy = any(p["ProcCode"] == "D1110" and p["ProcStatus"] == 2
                            and 0 <= days_ago(p["ProcDate"]) <= 91 for p in procs)
        if recent_prophy != ("EX2_recent_prophy" in te):
            ex2_mismatch += 1
        # (3) eligible flag = no failed inclusion AND no triggered exclusion
        if se["eligible"] != (not fi and not te):
            elig_mismatch += 1
        # (3) every evaluable truth/med-based exclusion independently derived from labelled
        # truth (not from `se`'s own lists) -- catches a mispopulated triggered_exclusion.
        prof, med = r["profile"], r.get("medical", {})
        tc = {c["key"]: c for c in med.get("true_conditions", [])}
        tm = {m["key"] for m in med.get("true_medications", [])}
        recent = med.get("recent_medications", [])
        uncontrolled = any(tc[k].get("controlled") is False
                           for k in ("t2dm", "t1dm", "htn", "cancer") if k in tc)
        want = {
            "EX6_premed": bool({"prosthetic_joint", "heart_valve"} & set(tc)),
            "EX7_tmd": "tmd" in tc,
            "EX9_tobacco": prof["smoker"] or "tobacco" in tc,
            "EX10_uncontrolled": uncontrolled,
            "EX11_pregnancy": "pregnancy" in tc,
            "EX12_hyperplasia_med": bool({"amlodipine", "phenytoin", "cyclosporine"} & tm)
                                    or any(x["class"] == "hyperplasia_drug" for x in recent),
            "EX13_antibiotics": any(x["class"] == "antibiotic" and x["days_ago"] <= 91 for x in recent),
            "EX14_steroid_nsaid": "prednisone" in tm,
            "EX15_anticoagulant": bool({"warfarin", "apixaban", "rivaroxaban", "clopidogrel"} & tm),
            "EX16_cardiac_device": "pacemaker" in tc,
        }
        for exk, expected in want.items():
            if expected != (exk in te):
                truth_ex_mismatch += 1

    check(checked > 0, f"adults evaluated ({checked}, charted + uncharted)")
    check(site_mismatch == 0, f"qualifying_site_count matches SQL BOP+PD>=4 recount ({site_mismatch} bad)")
    check(ic3_mismatch == 0, f"IC3 membership matches recomputed site count>=8 ({ic3_mismatch} bad)")
    check(teeth_mismatch == 0, f"natural_teeth matches SQL current-exam tooth count ({teeth_mismatch} bad)")
    check(ic5_mismatch == 0, f"IC5 membership matches recomputed teeth/quadrant rule ({ic5_mismatch} bad)")
    check(ic1_mismatch == 0, f"IC1 membership matches age 22-75 ({ic1_mismatch} bad)")
    check(ic2_mismatch == 0, f"IC2 membership matches true stage I-III & grade A/B ({ic2_mismatch} bad)")
    check(mob_mismatch == 0, f"EX5 mobility matches SQL mobility>2 ({mob_mismatch} bad)")
    check(ic4_mismatch == 0, f"IC4 declined-SRP matches SQL treatment-planned SRP ({ic4_mismatch} bad)")
    check(ex1_mismatch == 0, f"EX1 recent SRP/surgery matches SQL procedure dates ({ex1_mismatch} bad)")
    check(ex2_mismatch == 0, f"EX2 recent prophy matches SQL D1110 dates ({ex2_mismatch} bad)")
    check(elig_mismatch == 0, f"eligible flag == (no failed inclusion & no triggered exclusion) ({elig_mismatch} bad)")
    check(truth_ex_mismatch == 0, f"all evaluable exclusions independently match labelled truth ({truth_ex_mismatch} bad)")

    n_elig = sum(1 for r in doc["patients"] if r.get("study_eligibility", {}).get("eligible"))
    check(n_elig > 0, f"a non-empty truly-eligible cohort exists ({n_elig} patients)")

    print("\nAll study-eligibility checks passed." if not failures
          else f"\nFAIL: {len(failures)} failing check(s)")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
