#!/usr/bin/env python3
"""CI gate on the generator's statistical-fidelity report.

Usage:  python tests/check_fidelity.py <fidelity.json>
(produced by:  generate.py --fidelity-report <fidelity.json>)

The generator is the single source of the fidelity logic; this script just enforces its
verdict, exiting non-zero if any GATED metric drifts outside tolerance. Informational
(ungated, low-N) metrics are printed but never fail the build.
"""
import json, os, sys


def fmt(v):
    if isinstance(v, list):
        return "[" + " ".join(f"{x:.2f}" for x in v) + "]"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def main():
    if len(sys.argv) != 2:
        print("usage: check_fidelity.py <fidelity.json>")
        sys.exit(2)
    path = sys.argv[1]
    with open(path) as f:
        rep = json.load(f)
    meta = rep["meta"]
    print(f"\n=== Fidelity gate: {os.path.basename(path)} "
          f"(n={meta['adults_profiled']} adults, seed={meta['seed']}) ===")
    if meta["flags"]["stage_lock"] or meta["flags"]["grade_lock"]:
        print(f"  locks active: stage={meta['flags']['stage_lock']} grade={meta['flags']['grade_lock']}")

    fails = []
    for m in rep["metrics"]:
        if not m["gated"]:
            print(f"  info: {m['name']:<22} obs {fmt(m['observed'])} vs exp {fmt(m['expected'])}")
            continue
        status = "PASS" if m["pass"] else "FAIL"
        print(f"  {status}: {m['name']:<22} obs {fmt(m['observed'])} vs exp {fmt(m['expected'])} "
              f"(dev {m['deviation']} <= tol {m['tolerance']})")
        if not m["pass"]:
            fails.append(m)

    print(f"\n  {rep['gated_passed']}/{rep['gated_count']} gated metrics pass "
          f"({len(rep['metrics']) - rep['gated_count']} informational)")
    if fails or not rep["all_pass"]:
        print("FIDELITY GATE FAILED:")
        for m in fails:
            print(f"   -> {m['name']}: {m['detail']}"
                  + (f"  [{m['note']}]" if m.get("note") else ""))
        sys.exit(1)
    print("FIDELITY GATE PASSED")


if __name__ == "__main__":
    main()
