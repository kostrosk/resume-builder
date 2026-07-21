"""
interview.py — turn a posting's gaps into questions, and your answers into
experiences.

    python interview.py jd/acme.md
    python interview.py jd/acme.md --limit 5

For each high-value term the posting wants that nothing confirmed covers, it:

  1. shows the term and the posting's own line using it, so you know what
     they mean by it
  2. shows the nearest thing already in your library — often the honest
     answer is "confirm that one", not "write something new"
  3. asks whether you actually did work like this, and listens

Your answer, in your words, becomes the experience — verbatim. The tool never
suggests wording, never proposes a number, and never fills a silence: skip a
question and the gap stays a gap, which is the truthful outcome. You are asked
directly whether you would defend the sentence in an interview; only a yes
marks it confirmed.

Everything written is appended to data/experiences.yaml (timestamped backup
first) with tier: interviewed, and is yours to edit like any other entry.
"""
import os, re, sys, shutil, argparse, datetime, yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tailor as T

ROOT = os.path.dirname(os.path.abspath(__file__))
EXPS = os.path.join(ROOT, "data", "experiences.yaml")


def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def gap_terms(jdw, confirmed, jobs, limit):
    """Highest-weight posting terms with no confirmed coverage."""
    body = " ".join(e["text"].get("long", "") for e in confirmed)
    body += " " + " ".join(f"{j.get('role','')} {j.get('company','')}"
                           for j in jobs.values())
    tagtext = " ".join(" ".join(str(t) for t in e.get("tags") or [])
                       for e in confirmed)
    have = T.expand(set(T.toks(body + " " + tagtext)) |
                    T.phrases(body + " " + tagtext))
    ranked = sorted(jdw, key=lambda t: -jdw[t])
    out, seen = [], set()
    for t in ranked:
        if t in have or len(t) < 4:
            continue
        # skip terms subsumed by one already queued ("data govern framework"
        # after "govern framework") so you are not asked twice
        if any(t in s or s in t for s in seen):
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= limit:
            break
    return out


def posting_line(term, jd_text):
    words = term.split()
    for ln in jd_text.splitlines():
        low = ln.lower()
        if all(w[:6] in low for w in words):
            return ln.strip("-• \t")
    return ""


def nearest(term, exps):
    tt = T.expand({term})
    best, score = None, 0
    for e in exps:
        body = e["text"].get("long", "")
        terms = T.expand(set(T.toks(body)) | T.phrases(body))
        ov = len(tt & terms) + sum(0.5 for w in term.split() if w in terms)
        if ov > score:
            best, score = e, ov
    return best


def append_experiences(entries):
    """Append new entries to the library, backup first, verify after."""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{EXPS}.{stamp}.bak"
    shutil.copy2(EXPS, backup)
    block = yaml.safe_dump(entries, sort_keys=False, allow_unicode=True, width=100)
    with open(EXPS, "a", encoding="utf-8") as f:
        if not open(EXPS, encoding="utf-8").read().endswith("\n"):
            f.write("\n")
        f.write(block)
    try:
        yaml.safe_load(open(EXPS, encoding="utf-8"))
    except yaml.YAMLError as e:
        shutil.copy2(backup, EXPS)
        sys.exit(f"ERROR: append produced invalid YAML ({e}); restored {backup}")
    return backup


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jd")
    ap.add_argument("--limit", type=int, default=8)
    a = ap.parse_args()

    jdp = a.jd if os.path.exists(a.jd) else os.path.join(ROOT, a.jd)
    if not os.path.exists(jdp):
        sys.exit(f"ERROR: no such posting: {a.jd}")
    meta, jd_text = T.jd_meta(open(jdp, encoding="utf-8").read())

    cfg, jobs, confirmed, _ = T.load()
    alldoc = yaml.safe_load(open(EXPS, encoding="utf-8")) or {}
    everyone = alldoc.get("experiences") or []
    jdw = T.jd_terms(jd_text)
    gaps = gap_terms(jdw, confirmed, jobs, a.limit)

    title = " — ".join(x for x in (meta.get("role"), meta.get("company")) if x) \
        or os.path.basename(jdp)
    print(f"\n{title}: {len(gaps)} uncovered term(s) worth asking about.")
    print("Answer in your own words, past tense. Enter skips — a skipped gap")
    print("stays a gap, which is the honest result. Ctrl+C quits, nothing lost.\n")

    jobids = list(jobs)
    new = []
    for i, term in enumerate(gaps, 1):
        print("=" * 70)
        print(f"[{i}/{len(gaps)}] The posting wants:  {term.upper()}")
        line = posting_line(term, jd_text)
        if line:
            print(f'   their words: "{line[:160]}"')
        near = nearest(term, everyone)
        if near is not None:
            state = "CONFIRMED" if near.get("confirmed") is True else "unconfirmed"
            print(f"   closest in your library ({state}): {near['id']}")
            print(f"      {near['text'].get('long','')[:150]}")
            if near.get("confirmed") is not True:
                print("      -> if that covers it, confirm THAT (python confirm.py) "
                      "instead of writing something new.")
        ans = ask("\n   Did you do work like this? Describe it (Enter = skip):\n   > ")
        if not ans:
            print("   skipped — stays a gap.\n")
            continue
        job = ""
        while job not in jobids:
            job = ask(f"   Which job was this at? {jobids}: ")
            if not job:
                break
        metrics = []
        num = ask("   A number you measured, if any (Enter = none — never guess): ")
        if num:
            kind = ""
            while kind not in ("measured", "target"):
                kind = ask("   Was that a measured result or a target you set? "
                           "[measured/target]: ").lower()
            metrics.append({"value": num, "kind": kind, "context": term})
        defend = ask("   Would you defend that sentence, as written, in an "
                     "interview? [y/N]: ").lower()
        eid = "interview-" + re.sub(r"[^a-z0-9]+", "-",
                                    " ".join(ans.lower().split()[:5])).strip("-")
        new.append({
            "id": eid, "job": job or "TODO", "project": "",
            "confirmed": defend == "y",
            "tier": "interviewed",
            "tags": [term] + [t for t in term.split() if len(t) > 4][:2],
            "metrics": metrics,
            "text": {"long": ans, "medium": "", "short": ""},
        })
        print(f"   recorded as {eid}  (confirmed: {defend == 'y'})\n")

    if not new:
        print("\nNothing added. The gaps file still lists what is missing.")
        return
    backup = append_experiences(new)
    conf = sum(1 for e in new if e["confirmed"])
    print("=" * 70)
    print(f"added {len(new)} experience(s) ({conf} confirmed) to data/experiences.yaml")
    print(f"backup at {os.path.basename(backup)} — entries are yours to edit")
    print(f"\nrebuild to see the difference:  python run.py {a.jd}")


if __name__ == "__main__":
    main()
