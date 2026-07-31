#!/usr/bin/env python3
"""QA validator for the perio feature. Parses a generated .sql dump and checks the
clinical/schema invariants of the DEFAULT (realistic) generation mode.

Usage:  python tests/qa_validate.py <generated.sql>
(or run tests/run_qa.sh to generate fixtures and run the whole suite).
"""
import re, sys, os
from collections import defaultdict
from datetime import date, datetime

failures = []
def check(cond, msg):
    if cond:
        print(f"  PASS: {msg}")
    else:
        print(f"  FAIL: {msg}")
        failures.append(msg)

def split_vals(s):
    """Split a VALUES tuple body on top-level commas, respecting single quotes."""
    out, cur, q, i = [], [], False, 0
    while i < len(s):
        c = s[i]
        if c == "'" :
            q = not q
            cur.append(c)
        elif c == "\\" and q and i+1 < len(s):
            cur.append(c); cur.append(s[i+1]); i += 2; continue
        elif c == "," and not q:
            out.append("".join(cur).strip()); cur = []
        else:
            cur.append(c)
        i += 1
    out.append("".join(cur).strip())
    return out

INSERT_RE = re.compile(r"^INSERT INTO `(\w+)` \((.*?)\) VALUES \((.*)\);$")

def parse(path):
    rows = defaultdict(list)
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            m = INSERT_RE.match(line)
            if not m:
                continue
            table, cols, vals = m.group(1), m.group(2), m.group(3)
            colnames = [c.strip() for c in cols.split(",")]
            v = split_vals(vals)
            if len(colnames) != len(v):
                rows["_PARSE_ERROR"].append((table, len(colnames), len(v), line[:120]))
                continue
            d = {}
            for cn, vv in zip(colnames, v):
                if vv == "NULL":
                    d[cn] = None
                elif vv.startswith("'"):
                    d[cn] = vv[1:-1]
                else:
                    try:
                        d[cn] = int(vv)
                    except ValueError:
                        try: d[cn] = float(vv)
                        except ValueError: d[cn] = vv
            rows[table].append(d)
    return rows

def main():
    sqlpath = sys.argv[1]
    rows = parse(sqlpath)
    print(f"\n=== Parsing {os.path.basename(sqlpath)} ===")
    check(not rows.get("_PARSE_ERROR"), f"all INSERTs parse cleanly ({len(rows.get('_PARSE_ERROR', []))} errors)")
    if rows.get("_PARSE_ERROR"):
        for e in rows["_PARSE_ERROR"][:5]:
            print("    ", e)

    patients = {p["PatNum"]: p for p in rows["patient"]}
    exams = rows["perioexam"]
    meas = rows["periomeasure"]
    procs = rows["procedurelog"]
    proccodes = {pc["CodeNum"]: pc["ProcCode"] for pc in rows["procedurecode"]}
    # procedurelog stores CodeNum, not ProcCode -> attach the code string
    for p in procs:
        p["ProcCode"] = proccodes.get(p["CodeNum"])

    print(f"  ({len(patients)} patients, {len(exams)} exams, {len(meas)} measures, {len(procs)} procedures)")

    # --- adults only ---
    today = date.today()
    def age(pat):
        bd = datetime.strptime(pat["Birthdate"], "%Y-%m-%d").date()
        return (today - bd).days // 365
    exam_pats = {e["PatNum"] for e in exams}
    non_adult = [pn for pn in exam_pats if age(patients[pn]) < 18]
    check(not non_adult, f"all perio-charted patients are adults >=18 ({len(non_adult)} minors charted)")

    # --- new procedure codes present ---
    for code in ("D4260", "D4261", "D4381"):
        check(code in proccodes.values(), f"new code {code} present in procedurecode rows")

    # --- medical history: structural FK + adults-only (present unless --no-medical) ---
    diseasedefs = {d["DiseaseDefNum"] for d in rows.get("diseasedef", [])}
    medicationdefs = {m["MedicationNum"]: m for m in rows.get("medication", [])}
    allergydefs = {a["AllergyDefNum"] for a in rows.get("allergydef", [])}
    diseases = rows.get("disease", [])
    medpats = rows.get("medicationpat", [])
    allergies = rows.get("allergy", [])
    if diseases or medpats or allergies:
        med_pats = ({d["PatNum"] for d in diseases} | {m["PatNum"] for m in medpats}
                    | {a["PatNum"] for a in allergies})
        check(all(pn in patients for pn in med_pats), "every medical PatNum resolves to a patient")
        check(all(age(patients[pn]) >= 18 for pn in med_pats), "medical history is adults-only")
        check(all(d["DiseaseDefNum"] in diseasedefs for d in diseases)
              and all(m["MedicationNum"] in medicationdefs for m in medpats)
              and all(a["AllergyDefNum"] in allergydefs for a in allergies),
              "every disease/medicationpat/allergy FK resolves to its def table")
        check(all(m["RxCui"] == medicationdefs[m["MedicationNum"]]["RxCui"] for m in medpats),
              "medicationpat.RxCui matches its medication def")

    # --- SequenceType validity (never 5 SkipTooth or 7 CAL) ---
    seqs = defaultdict(int)
    for m in meas:
        seqs[m["SequenceType"]] += 1
    check(all(s in (0,1,2,3,4,6) for s in seqs), f"SequenceTypes only in {{0,1,2,3,4,6}}; got {sorted(seqs)}")
    check(7 not in seqs, "CAL (7) never stored")
    check(5 not in seqs, "SkipTooth (5) not emitted")

    # --- IntTooth range + no 3rd molars ---
    teeth = {m["IntTooth"] for m in meas}
    check(all(1 <= t <= 32 for t in teeth), f"IntTooth in 1..32 (got min {min(teeth)}, max {max(teeth)})")
    third = teeth & {1,16,17,32}
    check(not third, f"3rd molars (1/16/17/32) excluded (found {sorted(third)})")

    SITE_COLS = ["MBvalue","Bvalue","DBvalue","MLvalue","Lvalue","DLvalue"]
    def surfs(m): return [m[c] for c in SITE_COLS]

    # --- per-SequenceType encoding rules ---
    bad_probe = bad_mob = bad_furc = bad_bleed = bad_ging = bad_mgj = 0
    probe_vals = []
    for m in meas:
        st, tv, sv = m["SequenceType"], m["ToothValue"], surfs(m)
        if st == 4:  # Probing: ToothValue -1, surfaces 1..19 (we use 1..12)
            if tv != -1 or any(not (1 <= x <= 19) for x in sv): bad_probe += 1
            probe_vals += [x for x in sv if x >= 0]
        elif st == 0:  # Mobility: ToothValue 1..19, surfaces all -1
            if not (1 <= tv <= 19) or any(x != -1 for x in sv): bad_mob += 1
        elif st == 1:  # Furcation: ToothValue -1, surfaces -1..3 (we use 0..3)
            if tv != -1 or any(not (-1 <= x <= 19) for x in sv): bad_furc += 1
        elif st == 6:  # Bleeding bitmask: ToothValue -1, surfaces 0..15
            if tv != -1 or any(not (0 <= x <= 15) for x in sv): bad_bleed += 1
        elif st == 2:  # GingMargin: ToothValue -1; surfaces -1, 0..19, or 100..119 (coronal)
            if tv != -1 or any(not (x == -1 or 0 <= x <= 19 or 100 <= x <= 119) for x in sv): bad_ging += 1
        elif st == 3:  # MGJ: ToothValue -1; maxillary lingual sites -1
            if tv != -1: bad_mgj += 1
            if m["IntTooth"] <= 16 and (m["MLvalue"] != -1 or m["Lvalue"] != -1 or m["DLvalue"] != -1):
                bad_mgj += 1
    check(bad_probe == 0, f"Probing rows valid (ToothValue=-1, surfaces 1..19): {bad_probe} bad")
    check(bad_mob == 0, f"Mobility rows valid (grade in ToothValue, surfaces -1): {bad_mob} bad")
    check(bad_furc == 0, f"Furcation rows valid: {bad_furc} bad")
    check(bad_bleed == 0, f"Bleeding bitmask surfaces 0..15: {bad_bleed} bad")
    check(bad_ging == 0, f"GingMargin rows valid: {bad_ging} bad")
    check(bad_mgj == 0, f"MGJ maxillary-lingual rule honored: {bad_mgj} bad")
    if probe_vals:
        check(max(probe_vals) <= 12, f"probing depths clamped <=12mm (max {max(probe_vals)})")

    # --- CAL-driven model: stage is set by CAL (=PD+GingMargin), PD is derived ---
    def decode_ging(g): return (100 - g) if g >= 100 else g
    probe_by, ging_by = {}, {}
    for m in meas:
        key = (m["PerioExamNum"], m["IntTooth"])
        if m["SequenceType"] == 4: probe_by[key] = surfs(m)
        elif m["SequenceType"] == 2: ging_by[key] = surfs(m)
    cal_vals, deep_pd, pseudo, max_cal = [], 0, 0, 0
    for key, pds in probe_by.items():
        gs = ging_by.get(key, [0]*6)
        for pd, g in zip(pds, gs):
            if pd < 0: continue
            margin = decode_ging(g)
            cal = pd + margin
            cal_vals.append(cal); max_cal = max(max_cal, cal)
            if pd >= 6: deep_pd += 1
            if margin < 0: pseudo += 1
    check(cal_vals and min(cal_vals) >= 0, f"all computed CAL (PD+GingMargin) are >=0 (min {min(cal_vals) if cal_vals else 'NA'})")
    check(max_cal <= 15, f"computed CAL stays clinically plausible (max {max_cal}mm)")
    check(deep_pd > 0, f"deep probing pockets (>=6mm) occur in the realistic mix ({deep_pd} sites)")
    check(pseudo > 0, f"pseudopockets (coronal/negative gingival margin) present ({pseudo} sites)")

    # --- every exam has >=1 probing measure; every measure has a parent exam ---
    exam_nums = {e["PerioExamNum"] for e in exams}
    meas_exam = {m["PerioExamNum"] for m in meas}
    check(meas_exam <= exam_nums, "every periomeasure references an existing perioexam")
    exams_with_probe = {m["PerioExamNum"] for m in meas if m["SequenceType"] == 4}
    check(exams_with_probe == exam_nums, "every exam has probing measurements")

    # --- exam PatNum FK + ProvNum valid ---
    check(all(e["PatNum"] in patients for e in exams), "every exam references an existing patient")
    provs = {pr["ProvNum"] for pr in rows["provider"]}
    check(all(e["ProvNum"] in provs for e in exams), "every exam references an existing provider")

    # --- treatment coherence ---
    # procedures by patient
    proc_by_pat = defaultdict(list)
    for p in procs:
        proc_by_pat[p["PatNum"]].append(p)
    def has_code(pn, code):
        return any(x["ProcCode"] == code for x in proc_by_pat[pn])

    # periodontitis patients (have SRP) should also have D0180 and (once enough time
    # has passed since therapy) D4910 maintenance. Only COMPLETED SRP (ProcStatus=2)
    # counts as treatment -- a treatment-PLANNED SRP (ProcStatus=1) is the "declined SRP"
    # recruitment signal (see generate.py _generate_study_signals), not actual therapy.
    srp_pats = {p["PatNum"] for p in procs if p["ProcCode"] in ("D4341","D4342") and p["ProcStatus"] == 2}
    def earliest_srp(pn):
        ds = [p["ProcDate"] for p in proc_by_pat[pn]
              if p["ProcCode"] in ("D4341","D4342") and p["ProcStatus"] == 2]
        return min(datetime.strptime(d, "%Y-%m-%d").date() for d in ds)
    miss_eval = [pn for pn in srp_pats if not has_code(pn,"D0180")]
    # only require maintenance for patients whose SRP was >200 days ago
    established = [pn for pn in srp_pats if (today - earliest_srp(pn)).days > 200]
    miss_maint = [pn for pn in established if not has_code(pn,"D4910")]
    check(not miss_eval, f"every SRP patient has a comprehensive perio eval D0180 ({len(miss_eval)} missing)")
    check(not miss_maint, f"every established SRP patient (>200d) has D4910 maintenance "
                          f"({len(miss_maint)}/{len(established)} missing)")

    # healthy charted patients (charted but never periodontitis) should have NO SRP
    # identify periodontitis pats via presence of D0180 or SRP
    perio_pats = {p["PatNum"] for p in procs if p["ProcCode"] in ("D4341","D4342","D0180","D4910","D4260","D4261")}
    healthy_charted = exam_pats - perio_pats
    healthy_with_srp = [pn for pn in healthy_charted if has_code(pn,"D4341") or has_code(pn,"D4342")]
    check(not healthy_with_srp, f"healthy-charted patients have no SRP ({len(healthy_with_srp)} violations)")

    # no appointment mixes D1110 and D4910 (no double cleaning in one visit)
    # group procedures by AptNum
    appt_codes = defaultdict(set)
    for p in procs:
        if p["AptNum"]:
            appt_codes[p["AptNum"]].add(p["ProcCode"])
    dbl = [a for a,c in appt_codes.items() if "D1110" in c and "D4910" in c]
    check(not dbl, f"no appointment has both D1110 and D4910 ({len(dbl)} double-cleaning visits)")

    # --- maintenance recall is individualized, not a fixed 90-day interval ---
    import statistics as _st
    d4910_dates = defaultdict(list)
    for p in procs:
        if p["ProcCode"] == "D4910":
            d4910_dates[p["PatNum"]].append(datetime.strptime(p["ProcDate"], "%Y-%m-%d").date())
    intervals = []
    for pn, ds in d4910_dates.items():
        ds = sorted(set(ds))
        intervals += [(b - a).days for a, b in zip(ds, ds[1:])]
    if intervals:
        sd = _st.pstdev(intervals)
        distinct_months = {round(x / 30.4) for x in intervals}
        print(f"  [maintenance recall] n={len(intervals)} intervals, mean {_st.mean(intervals)/30.4:.1f}mo, "
              f"stdev {sd:.0f}d, range {min(intervals)}-{max(intervals)}d")
        check(sd > 20, f"recall interval is individualized, not fixed (stdev {sd:.0f}d > 20)")
        check(len(distinct_months) >= 3, f"recall spans multiple cadence tiers ({sorted(distinct_months)} months)")

    # --- longitudinal coherence: treated patients improve after SRP ---
    # mean probing depth per exam, ordered by date, per patient
    exam_date = {e["PerioExamNum"]: e["ExamDate"] for e in exams}
    exam_pat = {e["PerioExamNum"]: e["PatNum"] for e in exams}
    pd_by_exam = defaultdict(list)
    for m in meas:
        if m["SequenceType"] == 4:
            pd_by_exam[m["PerioExamNum"]] += [x for x in surfs(m) if x >= 0]
    examsByPat = defaultdict(list)
    for en in exam_nums:
        if en in pd_by_exam and pd_by_exam[en]:
            mean_pd = sum(pd_by_exam[en])/len(pd_by_exam[en])
            examsByPat[exam_pat[en]].append((exam_date[en], mean_pd, en))
    def split(pats):
        imp = sm = wo = 0
        for pn in pats:
            lst = examsByPat.get(pn, [])
            if len(lst) < 2: continue
            lst.sort()
            base, last = lst[0][1], lst[-1][1]
            if last < base - 0.3: imp += 1
            elif last > base + 0.3: wo += 1
            else: sm += 1
        return imp, sm, wo

    # (a) healthy-charted patients should stay roughly FLAT over time
    hi, hs, hw = split(healthy_charted)
    htot = hi + hs + hw
    print(f"  [healthy charted] improved={hi}, stable={hs}, worsened={hw} (n={htot})")
    check(htot == 0 or hs / htot >= 0.80, f"healthy patients stay stable over time ({100*hs/max(1,htot):.0f}% stable, want >=80%)")

    # (b) treated periodontitis patients should show the post-SRP drop:
    #     mean PD at the re-eval/second exam < baseline exam.
    treated_drop = treated_total = 0
    for pn in srp_pats:
        lst = sorted(examsByPat.get(pn, []))
        if len(lst) < 2: continue
        treated_total += 1
        if lst[1][1] < lst[0][1] - 0.2:
            treated_drop += 1
    print(f"  [treated] {treated_drop}/{treated_total} show a post-SRP probing-depth drop at re-eval")
    check(treated_total == 0 or treated_drop / treated_total >= 0.80,
          f"treated patients show SRP improvement ({100*treated_drop/max(1,treated_total):.0f}%, want >=80%)")

    # treated patients should not MOSTLY end up worse than their pre-treatment baseline
    # (treatment should leave a lasting net benefit for the majority).
    tri, trs, trw = split(srp_pats)
    trtot = tri + trs + trw
    print(f"  [treated full-span vs baseline] better={tri}, ~same={trs}, worse={trw} (n={trtot})")
    check(trtot == 0 or trw / trtot <= 0.35,
          f"most treated patients are not worse than baseline long-term ({100*trw/max(1,trtot):.0f}% worse, want <=35%)")

    # (c) overall: diversity of trajectories exists (some improve, some worsen, some same)
    ti, ts, tw = split(examsByPat.keys())
    print(f"  [all charted] improved={ti}, stable={ts}, worsened={tw}")
    check(ti > 0 and tw > 0 and ts > 0, "trajectory diversity: some improve, some stay same, some worsen")
    check(any(len(v) >= 2 for v in examsByPat.values()), "patients have multi-visit longitudinal series")

    # ---- ItemOrder is a 0-BASED DISPLAY POSITION, never a primary key -----------------------------
    # Regression gate for the defect that broke the Open Dental CLIENT outright (2026-07-27 .. 07-30):
    # the emitters passed the row's own id as ItemOrder, so `operatory` carried 100,101,102,103 in a
    # four-row table. The Appointments module indexes its operatory-column list BY ItemOrder, so the
    # client threw an unhandled "Index was out of range" in ControlAppt.ModuleSelected on every launch.
    # Privara never noticed because it only ever READS. Contiguous-from-zero is the invariant.
    ops = sorted(int(o["ItemOrder"]) for o in rows["operatory"])
    check(ops == list(range(len(ops))),
          f"operatory.ItemOrder is 0-based and contiguous (got {ops})")

    provs = sorted(int(p["ItemOrder"]) for p in rows["provider"] if "ItemOrder" in p)
    check(not provs or provs == list(range(len(provs))),
          f"provider.ItemOrder is 0-based and contiguous (got {provs})")

    defsByCat = {}
    for d in rows["definition"]:
        defsByCat.setdefault(int(d["Category"]), []).append(int(d["ItemOrder"]))
    for cat, orders in sorted(defsByCat.items()):
        orders = sorted(orders)
        check(orders == list(range(len(orders))),
              f"definition.ItemOrder is 0-based within category {cat} (got {orders})")

    return failures

if __name__ == "__main__":
    f = main()
    print("\n=== RESULT ===")
    if f:
        print(f"{len(f)} FAILURE(S)")
        sys.exit(1)
    print("ALL CHECKS PASSED")
