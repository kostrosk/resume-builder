"""
test_guardrails.py — proves the rewrite checks actually block what they claim to.

    python test_guardrails.py

These are the checks that stop an AI rewrite from drifting away from what you
confirmed. If any case fails, --llm is not safe to use.
"""
import sys, os, yaml
from tailor import check_rewrite, verb_tier

ROOT = os.path.dirname(os.path.abspath(__file__))
# Your real config is gitignored, so on a fresh clone only the example exists.
# This test has to run for someone who just cloned the repo — it is the proof
# that --llm is safe, and proof you cannot run is worth nothing.
CFG = os.path.join(ROOT, "config", "resume-config.yaml")
if not os.path.exists(CFG):
    CFG = os.path.join(ROOT, "config", "resume-config.example.yaml")
RULES = yaml.safe_load(open(CFG, encoding="utf-8"))["rewrite"]["guardrails"]

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
    ("Leading a data catalog in OpenMetadata, documenting 40 tables.",
     False, "gerund escalation: helped -> leading"),
    ("Owning a data catalog in OpenMetadata, documenting 40 tables.",
     False, "gerund escalation: helped -> owning"),
    ("Building a data catalog in OpenMetadata, 40 tables.",
     False, "gerund escalation: helped -> building"),
]

# The ladder must not read a noun as a verb. "governance" is not "governed";
# treating it as one invents a leadership claim nobody made.
NOUN_CASES = [
    ("Data governance operating model rolled out across 12 domains.", 0),
    ("Governance council chartered with decision rights.", 0),
    ("Leading the governance council.", 3),
    ("Helped establish the governance council.", 1),
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

    print()
    for text, expect in NOUN_CASES:
        got = verb_tier(text)
        good = got == expect
        label = f"verb rung {expect} for {text!r}"
        if not good:
            fails.append(label)
        print(f"{'PASS' if good else 'FAIL'}  rung {got}    {text}")

    total = len(CASES) + len(NOUN_CASES)
    print(f"\n{total - len(fails)}/{total} passed")
    if fails:
        print("\nGUARDRAILS ARE NOT SAFE — do not use --llm until these pass:")
        for f in fails:
            print(f"  - {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
