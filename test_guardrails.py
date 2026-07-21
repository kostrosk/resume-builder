"""
test_guardrails.py — proves the rewrite checks actually block what they claim to.

    python test_guardrails.py

These are the checks that stop an AI rewrite from drifting away from what you
confirmed. If any case fails, --llm is not safe to use.
"""
import sys, os, yaml
from tailor import check_rewrite

ROOT = os.path.dirname(os.path.abspath(__file__))
RULES = yaml.safe_load(open(os.path.join(ROOT, "config", "resume-config.yaml"),
                            encoding="utf-8"))["rewrite"]["guardrails"]

SRC = "Helped establish a data catalog in OpenMetadata, documenting 40 critical tables."

CASES = [
    ("Helped establish a data catalog in OpenMetadata; 40 critical tables.",
     True,  "shorter, same leading verb"),
    ("Supported a data catalog in OpenMetadata covering 40 tables.",
     True,  "shorter, sideways verb (helped -> supported)"),
    ("Established a data catalog in OpenMetadata; documented 40 critical tables.",
     False, "quiet promotion: 'helped establish' -> 'established'"),
    ("Led enterprise data catalog in OpenMetadata, documenting 40 tables.",
     False, "scope escalation: helped -> led"),
    ("Established a data catalog in OpenMetadata, documenting 400 tables.",
     False, "invented number: 40 -> 400"),
    ("Established a data catalog in Collibra, documenting 40 tables.",
     False, "swapped tool: OpenMetadata -> Collibra"),
    ("Established a catalog in OpenMetadata for the Snowflake estate, 40 tables.",
     False, "added a system that was never mentioned"),
    ("Built a governed data catalog in OpenMetadata covering 40 critical tables "
     "across the enterprise estate.",
     False, "longer than the original"),
    ("Designed and implemented a data catalog in OpenMetadata, 40 tables.",
     False, "designed -> implemented is an escalation"),
]


def main():
    fails = []
    print(f"source: {SRC}\n")
    for new, expect, label in CASES:
        ok, why = check_rewrite(SRC, new, RULES)
        good = ok == expect
        if not good:
            fails.append(label)
        print(f"{'PASS' if good else 'FAIL'}  {'accept' if ok else 'reject'}  {label}")
        if why:
            print(f"          {'; '.join(why)}")
    print(f"\n{len(CASES) - len(fails)}/{len(CASES)} passed")
    if fails:
        print("\nGUARDRAILS ARE NOT SAFE — do not use --llm until these pass:")
        for f in fails:
            print(f"  - {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
