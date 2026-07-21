"""
propose.py — read a job posting and tell you what to do about it.

    python propose.py jd/acme.md

Writes output/<name>-proposal.md, a worksheet answering three questions:

  1. Which of your experiences already match this posting, and why?
  2. Which experiences WOULD match but are not confirmed yet?
  3. Which words does the posting care about that nothing of yours covers,
     and which experience is closest to covering them?

It changes nothing. It proposes; you decide. Copy the suggested `match:`
lines into data/experiences.yaml to make an experience findable next time.
"""
import os, sys, re, argparse, yaml
from collections import defaultdict

import tailor as T

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "output")


def load_all():
    """Like tailor.load() but keeps unconfirmed rows, which is the point."""
    cfg = yaml.safe_load(open(T.CONF, encoding="utf-8"))
    doc = yaml.safe_load(open(T.EXPS, encoding="utf-8")) or {}
    jobs = {j["id"]: j for j in cfg.get("jobs", []) if j.get("enabled", True)}
    return cfg, jobs, doc.get("experiences", [])


def closest(term, exps, mcfg, k=2):
    """Which experiences are nearest to covering a term you currently miss."""
    out = []
    tt = T.expand({term})
    for e in exps:
        body = e["text"].get("long", "")
        terms = T.expand(set(T.toks(body)) | T.phrases(body))
        ov = len(tt & terms)
        # partial credit for sharing a word with a multiword term
        words = set(term.split())
        ov += sum(0.5 for w in words if w in terms)
        if ov:
            out.append((ov, e))
    out.sort(key=lambda x: -x[0])
    return [e for _s, e in out[:k]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jd")
    a = ap.parse_args()

    jdp = a.jd if os.path.exists(a.jd) else os.path.join(ROOT, a.jd)
    if not os.path.exists(jdp):
        print(f"ERROR: no such posting: {a.jd}")
        sys.exit(1)

    jd_text = open(jdp, encoding="utf-8").read()
    name = os.path.splitext(os.path.basename(jdp))[0]
    title = next((l.strip("# ").strip() for l in jd_text.splitlines() if l.strip()), name)

    cfg, jobs, exps = load_all()
    mcfg = cfg.get("matching", {})
    pcfg = mcfg.get("propose", {})
    jdw = T.jd_terms(jd_text)
    profile, sig, s_, e_, ratio = T.classify(jd_text, title)

    rows = []
    for e in exps:
        if e.get("job") not in jobs or e.get("exclude"):
            continue
        band, raw, top = T.score(e, jdw, mcfg)
        rows.append({"e": e, "band": band, "raw": raw, "top": top})
    rows.sort(key=lambda r: -r["raw"])

    ready = [r for r in rows if r["e"].get("confirmed") and r["band"] >= 1]
    locked = [r for r in rows if not r["e"].get("confirmed") and r["band"] >= 1]

    # what the posting wants that nothing confirmed covers
    top_terms = sorted(jdw, key=lambda x: -jdw[x])[:50]
    body = " ".join(r["e"]["text"].get("long", "") for r in ready)
    have = T.expand(set(T.toks(body)) | T.phrases(body))
    for r in ready:
        have |= T.expand({" ".join(T.stem(x) for x in str(t).lower().split())
                          for t in (r["e"].get("tags") or []) + (r["e"].get("match") or [])})
    missing = [t for t in top_terms if t not in have]

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{name}-proposal.md")
    lim = pcfg.get("max_suggestions", 25)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# What to do about: {title}\n\n")
        f.write(f"- posting reads as **{profile}**\n")
        f.write(f"- {len(ready)} experiences ready to use, "
                f"{len(locked)} would match but are not confirmed\n")
        f.write(f"- {len(missing)} of the posting's top terms have no coverage\n\n")
        f.write("Nothing here changes your files. Decide, then edit "
                "`data/experiences.yaml` yourself.\n\n---\n\n")

        f.write("## 1. Ready to use — these will appear\n\n")
        f.write("| score | id | job | why it matched |\n|---|---|---|---|\n")
        for r in ready[:lim]:
            f.write(f"| {r['raw']:.0f} | `{r['e']['id']}` | {r['e']['job']} | "
                    f"{', '.join(r['top'][:4])} |\n")
        if not ready:
            f.write("| — | — | — | nothing confirmed matches this posting |\n")

        if locked and pcfg.get("show_unconfirmed", True):
            f.write("\n## 2. Locked — confirm these and they become usable\n\n")
            f.write("These score well but `confirmed: false`, so the builder "
                    "cannot see them. Set `confirmed: true` on any that are true.\n\n")
            f.write("| score | id | job | why it would match |\n|---|---|---|---|\n")
            for r in locked[:lim]:
                f.write(f"| {r['raw']:.0f} | `{r['e']['id']}` | {r['e']['job']} | "
                        f"{', '.join(r['top'][:4])} |\n")

        if missing and pcfg.get("suggest_tags", True):
            f.write("\n## 3. Uncovered — the posting wants these, you show none\n\n")
            f.write("For each, the nearest experience you already have. If that "
                    "experience really does cover it, add the term to its `match:` "
                    "list and it will score next time. **If it doesn't cover it, "
                    "leave it alone — that is a real gap, not a wording problem.**\n\n")
            for t in missing[:lim]:
                near = closest(t, [r["e"] for r in rows], mcfg)
                f.write(f"### `{t}`  (posting weight {jdw[t]:.1f})\n\n")
                if near:
                    for e in near:
                        mark = "" if e.get("confirmed") else "  ← unconfirmed"
                        f.write(f"- `{e['id']}`{mark}\n")
                        f.write(f"  > {e['text'].get('long','')[:150]}…\n")
                    f.write(f"\n  If true, add to `{near[0]['id']}`:\n\n")
                    f.write(f"  ```yaml\n  match:\n    - {t}\n  ```\n\n")
                else:
                    f.write("- nothing of yours is close. Real gap.\n\n")

        f.write("\n---\n\n## Knobs you can turn per experience\n\n")
        f.write("```yaml\n")
        f.write("match:  [operating model, decision rights]   # extra keywords, "
                "weighted highest\n")
        f.write("boost:  1.5      # multiply this experience's score\n")
        f.write("pin:    true     # always include it, whatever the posting says\n")
        f.write("exclude: true    # never include it\n")
        f.write("```\n")

    print(f"posting reads as   {profile}")
    print(f"ready to use       {len(ready)}")
    print(f"locked (confirm)   {len(locked)}")
    print(f"uncovered terms    {len(missing)}")
    print(f"\n  {path}")
    if locked:
        print(f"\ntop locked experience: {locked[0]['e']['id']} "
              f"(score {locked[0]['raw']:.0f}) — confirm it to use it")


if __name__ == "__main__":
    main()
