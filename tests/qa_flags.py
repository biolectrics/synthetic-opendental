#!/usr/bin/env python3
"""QA for the --stage / --grade test corner-case flags.

Usage:  python tests/qa_flags.py <dir-with-stage2.sql/stage3C.sql/gradeA.sql/gradeC.sql>
(tests/run_qa.sh generates these fixtures for you).
"""
import os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qa_validate import parse

SITE = ["MBvalue","Bvalue","DBvalue","MLvalue","Lvalue","DLvalue"]
# Stage is set by CAL (= Probing + GingMargin), NOT probing depth.
CAL_BAND_HI = {"I":2,"II":4,"III":9,"IV":13}   # max interdental CAL for the stage
CAL_DEFMIN  = {"I":1,"II":3,"III":5,"IV":5}    # worst-site CAL that makes it that stage
failures = []
def check(c,m):
    print(("  PASS: " if c else "  FAIL: ")+m)
    if not c: failures.append(m)

def decode_ging(g):
    """GingMargin: 100+ encodes a coronal (negative) margin -> actual = 100 - stored."""
    return (100 - g) if g >= 100 else g

def cal_and_pd(rows):
    """Return (per-patient max CAL, per-patient max PD, all PD, all CAL, deep-pocket count,
    pseudopocket count, periodontitis-patient set)."""
    proccodes = {pc["CodeNum"]: pc["ProcCode"] for pc in rows["procedurecode"]}
    exam_pat = {e["PerioExamNum"]: e["PatNum"] for e in rows["perioexam"]}
    probe, ging = {}, {}
    for m in rows["periomeasure"]:
        key = (m["PerioExamNum"], m["IntTooth"])
        if m["SequenceType"] == 4: probe[key] = [m[c] for c in SITE]
        elif m["SequenceType"] == 2: ging[key] = [m[c] for c in SITE]
    pat_maxcal, pat_maxpd = defaultdict(int), defaultdict(int)
    all_pd, all_cal, deep, pseudo = [], [], 0, 0
    for key, pds in probe.items():
        gs = ging.get(key, [0]*6)
        pn = exam_pat[key[0]]
        for pd, g in zip(pds, gs):
            if pd < 0: continue
            margin = decode_ging(g)
            cal = pd + margin
            all_pd.append(pd); all_cal.append(cal)
            pat_maxpd[pn] = max(pat_maxpd[pn], pd)
            pat_maxcal[pn] = max(pat_maxcal[pn], cal)
            if pd >= 6: deep += 1
            if margin < 0: pseudo += 1
    perio_codes = {cn for cn,c in proccodes.items() if c in ("D4341","D4342","D0180","D4910","D4260","D4261")}
    perio_pats = {p["PatNum"] for p in rows["procedurelog"] if p["CodeNum"] in perio_codes}
    return pat_maxcal, pat_maxpd, all_pd, all_cal, deep, pseudo, perio_pats

def check_stage(path, stage):
    print(f"\n=== --stage {stage}: {path.split('/')[-1]} ===")
    rows = parse(path)
    pat_maxcal, pat_maxpd, all_pd, all_cal, deep, pseudo, perio_pats = cal_and_pd(rows)
    hi = CAL_BAND_HI[stage]
    # THE KEY INVARIANT: stage is bounded by CAL, never crossing into the next stage.
    check(max(all_cal) <= hi, f"NO computed CAL exceeds stage {stage} band {hi}mm (global max CAL {max(all_cal)})")
    # ...but probing depth is FREE: deep isolated pockets (pseudopockets) are allowed.
    if stage in ("I","II"):
        check(max(all_pd) >= 6,
              f"stage {stage} CAN still show isolated deep pockets >=6mm (global max PD {max(all_pd)}, "
              f"{deep} deep sites) despite CAL<= {hi}")
        check(pseudo > 0, f"pseudopockets (coronal gingival margin) present ({pseudo} sites)")
    # periodontitis patients present and recognizably at this stage's CAL severity
    pp = [pat_maxcal[pn] for pn in perio_pats if pn in pat_maxcal]
    check(len(pp) > 0, f"periodontitis patients exist ({len(pp)})")
    at_stage = sum(1 for v in pp if v >= CAL_DEFMIN[stage])
    check(at_stage/max(1,len(pp)) >= 0.9,
          f">=90% of periodontitis patients reach stage {stage} CAL (>={CAL_DEFMIN[stage]}mm): {at_stage}/{len(pp)}")
    # healthy patients still generated (charted, low CAL, not perio)
    healthy = [pn for pn,v in pat_maxcal.items() if v <= 1 and pn not in perio_pats]
    check(len(healthy) > 0, f"healthy patients still generated and charted ({len(healthy)})")
    return rows

def longitudinal_worse_frac(rows):
    """Fraction of treated patients ending worse-than-baseline (mean PD)."""
    proccodes = {pc["CodeNum"]: pc["ProcCode"] for pc in rows["procedurecode"]}
    srp = {cn for cn,c in proccodes.items() if c in ("D4341","D4342")}
    # Only COMPLETED SRP (ProcStatus=2) is treatment; ProcStatus=1 is the treatment-planned
    # "declined SRP" recruitment signal, whose (untreated) patients must not count as treated.
    srp_pats = {p["PatNum"] for p in rows["procedurelog"] if p["CodeNum"] in srp and p["ProcStatus"] == 2}
    exam_pat = {e["PerioExamNum"]: e["PatNum"] for e in rows["perioexam"]}
    exam_date = {e["PerioExamNum"]: e["ExamDate"] for e in rows["perioexam"]}
    pd_by_exam = defaultdict(list)
    for m in rows["periomeasure"]:
        if m["SequenceType"] == 4:
            pd_by_exam[m["PerioExamNum"]] += [m[c] for c in SITE if m[c] >= 0]
    byPat = defaultdict(list)
    for en, vals in pd_by_exam.items():
        if vals: byPat[exam_pat[en]].append((exam_date[en], sum(vals)/len(vals)))
    worse = tot = 0
    for pn in srp_pats:
        lst = sorted(byPat.get(pn, []))
        if len(lst) < 2: continue
        tot += 1
        if lst[-1][1] > lst[0][1] + 0.3: worse += 1
    return worse, tot

if __name__ == "__main__":
    SC = sys.argv[1]
    check_stage(f"{SC}/stage2.sql", "II")
    check_stage(f"{SC}/stage3C.sql", "III")

    # grade differential: grade A should barely progress; grade C should progress a lot
    print("\n=== --grade differential (A vs C, no stage lock) ===")
    wa, ta = longitudinal_worse_frac(parse(f"{SC}/gradeA.sql"))
    wc, tc = longitudinal_worse_frac(parse(f"{SC}/gradeC.sql"))
    fa = wa/max(1,ta); fc = wc/max(1,tc)
    print(f"  grade A: {wa}/{ta} treated patients worsen long-term ({100*fa:.0f}%)")
    print(f"  grade C: {wc}/{tc} treated patients worsen long-term ({100*fc:.0f}%)")
    check(fa < fc, f"grade A progresses LESS than grade C ({100*fa:.0f}% < {100*fc:.0f}%)")
    check(fa <= 0.15, f"grade A barely progresses (<=15% worsen): {100*fa:.0f}%")

    print("\n=== RESULT ===")
    print(f"{len(failures)} FAILURE(S)" if failures else "ALL FLAG CHECKS PASSED")
    sys.exit(1 if failures else 0)
