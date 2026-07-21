"""
tailor.py — match a job description against your experience library and
build a one-page, ATS-safe .docx.

    python tailor.py jd/acme.md            deterministic, free, no model
    python tailor.py jd/acme.md --llm      AI shortens bullets to fit

Reads data/experiences.yaml and config/resume-config.yaml.
Only `confirmed: true` experiences are ever eligible. Unconfirmed content is
not filtered out at the end — it is never loaded, so it cannot leak.

Never reads source/draft/ — enforced in load().
"""
import os, re, sys, argparse, yaml
from collections import defaultdict

import render as R

ROOT = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(ROOT, "config", "resume-config.yaml")
EXPS = os.path.join(ROOT, "data", "experiences.yaml")
SYN = os.path.join(ROOT, "config", "synonyms.yaml")
OUT = os.path.join(ROOT, "output")
LIN = os.path.join(ROOT, "lineage")
FORBIDDEN = os.path.join(ROOT, "source", "draft")

STOP = set("""a an the and or of to in for with on at by from as is are was were be been being
this that these those it its our your their we i you they he she them us not no if then than
will would can could should may might must have has had do does did doing done more most other
such own same so too very just about into over under out up down off across per each any all
role position job candidate company team work working ability years year experience required
requirements responsibilities preferred qualifications plus strong excellent good ensure ensuring
including include includes etc via while within across also new using use used help helps""".split())


def die(m):
    print(f"ERROR: {m}", file=sys.stderr)
    sys.exit(1)


def stem(w):
    for s in ("ization", "izations", "ations", "ation", "ances", "ance", "ences", "ence",
              "ments", "ment", "ings", "ing", "ies", "ied", "ers", "er", "ed", "es", "s"):
        if len(w) > len(s) + 3 and w.endswith(s):
            return w[:-len(s)]
    return w


def toks(t):
    return [stem(w) for w in re.findall(r"[a-z0-9][a-z0-9+#/.\-]*", t.lower())
            if w not in STOP and len(w) > 2]


def phrases(t):
    ws = [w for w in re.findall(r"[a-z0-9][a-z0-9+#/\-]*", t.lower()) if len(w) > 1]
    out = set()
    for n in (2, 3):
        for i in range(len(ws) - n + 1):
            g = ws[i:i + n]
            if g[0] in STOP or g[-1] in STOP:
                continue
            out.add(" ".join(stem(x) for x in g))
    return out


def load_syn():
    g = []
    if os.path.exists(SYN):
        for ln in open(SYN, encoding="utf-8"):
            ln = ln.strip()
            if not ln or ln.startswith("#") or ":" not in ln:
                continue
            k, v = ln.split(":", 1)
            terms = [k.strip()] + [x.strip() for x in v.split(",") if x.strip()]
            g.append({" ".join(stem(w) for w in t.lower().split()) for t in terms})
    return g


SYNG = load_syn()


def expand(s):
    out = set(s)
    for g in SYNG:
        if s & g:
            out |= g
    return out


# ------------------------------------------------------------------- load
def load():
    if not os.path.exists(CONF):
        die("config/resume-config.yaml not found")
    if not os.path.exists(EXPS):
        die("data/experiences.yaml not found — run: python migrate.py")
    cfg = yaml.safe_load(open(CONF, encoding="utf-8"))
    doc = yaml.safe_load(open(EXPS, encoding="utf-8")) or {}
    raw = doc.get("experiences", [])
    # THE GATE: unconfirmed experiences are never loaded.
    exps = [e for e in raw if e.get("confirmed") is True]
    jobs = {j["id"]: j for j in cfg.get("jobs", []) if j.get("enabled", True)}
    return cfg, jobs, exps, len(raw) - len(exps)


# ---------------------------------------------------------------- scoring
def jd_terms(text):
    lines = text.splitlines()
    w = defaultdict(float)
    for i, ln in enumerate(lines):
        pos = 1.6 if i < len(lines) * 0.35 else 1.0
        bul = 1.5 if re.match(r"^\s*[-*•]|\d+\.", ln) else 1.0
        for t in set(toks(ln)):
            w[t] += pos * bul
        for p in phrases(ln):
            w[p] += pos * bul * 2.0
    return w


def score(exp, jdw, mcfg=None):
    """Three tiers of evidence that an experience fits this posting:
      body text   incidental language, weight 1
      tags        vocabulary you curated,       weight tag_weight
      match       keywords you added by hand,   weight match_weight
    `boost` multiplies the total; `pin` forces inclusion; `exclude` blocks it.
    """
    mcfg = mcfg or {}
    tw = mcfg.get("tag_weight", 2.5)
    mw = mcfg.get("match_weight", 3.0)
    body = exp["text"].get("long", "")
    terms = expand(set(toks(body)) | phrases(body))

    def keyset(vals):
        return expand({" ".join(stem(x) for x in str(v).lower().split()) for v in vals})

    tagterms = keyset(exp.get("tags") or [])
    matchterms = keyset(exp.get("match") or [])

    hit = {t: jdw[t] for t in terms if t in jdw}
    taghit = {t: jdw[t] * tw for t in tagterms if t in jdw}
    mathit = {t: jdw[t] * mw for t in matchterms if t in jdw}
    allhit = {**hit, **taghit, **mathit}
    raw = (sum(hit.values()) + sum(taghit.values()) + sum(mathit.values()))
    raw *= float(exp.get("boost", 1.0) or 1.0)
    if exp.get("pin"):
        raw += 1000                       # pinned always outranks the field
    band = 3 if raw >= 16 else 2 if raw >= 8 else 1 if raw >= 3 else 0
    top = sorted(allhit, key=lambda x: -allhit[x])[:6]
    return band, raw, top


SENIOR = {"vp": 4, "vice president": 4, "svp": 4, "head of": 4, "chief": 4,
          "senior director": 4, "executive": 3, "director": 3, "head": 3,
          "senior manager": 2, "manager": 2, "lead": 2, "principal": 2,
          "architect": 2, "analyst": 1, "engineer": 1, "specialist": 1}
STRAT = ("strategy", "operating model", "roadmap", "executive", "board", "council",
         "decision rights", "vision", "budget", "organizational", "stakeholder",
         "transformation", "influence")
EXEC = ("sql", "python", "dbt", "pipeline", "hands-on", "implement", "configure",
        "build", "develop", "automate", "script", "etl", "tagging", "masking", "query")


def classify(text, title):
    low = (title + " " + text[:1500]).lower()
    best = max([v for k, v in SENIOR.items() if k in low] or [0])
    s = sum(text.lower().count(w) for w in STRAT)
    e = sum(text.lower().count(w) for w in EXEC)
    r = s / max(e, 1)
    if best >= 4 or (best == 3 and r > 1.6):
        return "DIRECTOR+/VP", best, s, e, r
    if best == 3 or (best == 2 and r > 2.0):
        return "DIRECTOR", best, s, e, r
    if best == 2:
        return "SENIOR MANAGER/LEAD", best, s, e, r
    return "BELOW DIRECTOR", best, s, e, r


# ------------------------------------------------------ deterministic trim
def trim(text, budget_chars):
    """Shorten without inventing: drop trailing clauses at natural breaks."""
    if len(text) <= budget_chars:
        return text
    for sep in ("; ", ". ", ", and ", " — ", ", "):
        parts = text.split(sep)
        while len(parts) > 1 and len(sep.join(parts)) > budget_chars:
            parts.pop()
        cand = sep.join(parts).rstrip(" ,;—-")
        if len(cand) <= budget_chars and len(cand) > budget_chars * 0.45:
            return cand
    cut = text[:budget_chars].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;—-")


# ------------------------------------------------------- rewrite guardrails
NUMRE = re.compile(r"\d[\d,.]*%?")
WORDRE = re.compile(r"[A-Za-z][A-Za-z0-9&./\-]*")


def entities(text):
    """Proper nouns and acronyms only.

    A word capitalised because it starts a sentence is not an entity — treating
    it as one rejects every rewrite that opens with a different verb, which is
    most of them. Only ALL-CAPS tokens and mid-sentence capitals count.
    """
    out = set()
    for m in WORDRE.finditer(text):
        w = m.group(0)
        before = text[:m.start()].rstrip()
        at_start = (not before) or before[-1] in ".!?;:"
        if w.isupper() and len(w) >= 2:
            out.add(w.lower())
        elif w[0].isupper() and not at_start and len(w) > 2:
            out.add(w.lower())
    return out
# Verb strength ladder. A rewrite may keep or lower the rung; never raise it.
# "Helped establish" -> "Established" reads as a promotion from contributor to
# owner, which is exactly the drift this product exists to prevent.
#
# Written as (base, past) so every surface form can be generated. A gerund is
# the same claim as a past tense — "Leading the council" says exactly what "Led
# the council" says — so both have to sit on the same rung or the ladder has a
# hole in it.
VERB_TIER = {
    1: [("help", "helped"), ("assist", "assisted"), ("support", "supported"),
        ("contribute", "contributed"), ("participate", "participated"),
        ("collaborate", "collaborated"), ("aid", "aided"), ("advise", "advised"),
        ("consult", "consulted")],
    2: [("establish", "established"), ("build", "built"), ("create", "created"),
        ("develop", "developed"), ("design", "designed"), ("draft", "drafted"),
        ("propose", "proposed"), ("plan", "planned"), ("recommend", "recommended"),
        ("maintain", "maintained"), ("document", "documented"),
        ("coordinate", "coordinated"), ("run", "ran"), ("manage", "managed"),
        ("deliver", "delivered"), ("implement", "implemented"),
        ("deploy", "deployed"), ("launch", "launched"), ("automate", "automated"),
        ("migrate", "migrated"), ("configure", "configured")],
    3: [("lead", "led"), ("own", "owned"), ("direct", "directed"),
        ("drive", "drove"), ("head", "headed"), ("chair", "chaired"),
        ("found", "founded"), ("spearhead", "spearheaded"),
        ("institutionalize", "institutionalized"), ("govern", "governed"),
        ("orchestrate", "orchestrated")],
}


def _forms(base, past):
    """Every surface form of one verb: base, third person, gerund, past."""
    f = {base, past, base + "s"}
    if base.endswith("e"):
        f.add(base[:-1] + "ing")            # migrate -> migrating
    elif re.search(r"[^aeiou][aeiou][^aeiouwxy]$", base):
        f.add(base + base[-1] + "ing")      # plan -> planning
    else:
        f.add(base + "ing")                 # lead -> leading
    if base.endswith(("s", "sh", "ch", "x", "z")):
        f.add(base + "es")                  # establish -> establishes
    return f


TIER_OF = {form: tier for tier, verbs in VERB_TIER.items()
           for base, past in verbs for form in _forms(base, past)}


def verb_tier(text):
    """Rung of the leading verb — the one carrying the claim. Falls back to the
    strongest verb anywhere if the line does not open with one.

    Matches known verb forms exactly and never stems an arbitrary word into a
    verb. "governance" is a noun; reading it as "governed" would invent a
    leadership claim on the source side and block honest rewrites.
    """
    for m in re.finditer(r"[A-Za-z]+", text):
        t = TIER_OF.get(m.group(0).lower())
        if t:
            return t
        if m.start() > 40:
            break
    tiers = [TIER_OF[w.lower()] for w in re.findall(r"[A-Za-z]+", text)
             if w.lower() in TIER_OF]
    return max(tiers) if tiers else 0
SOFT = {"the", "a", "an", "and", "of", "to", "in", "for", "with", "on", "at", "by", "from"}


def check_rewrite(src, new, rules):
    """Ordinary code, not the model, decides whether a rewrite is allowed.
    Any failure means the rewrite is discarded and the original is used."""
    bad = []
    if rules.get("max_length_ratio") and len(new) > len(src) * rules["max_length_ratio"]:
        bad.append("longer than the original")
    if rules.get("no_new_numbers", True):
        snum, nnum = set(NUMRE.findall(src)), set(NUMRE.findall(new))
        extra = nnum - snum
        if extra:
            bad.append(f"introduced numbers not in the source: {sorted(extra)}")
    if rules.get("no_new_entities", True):
        sent = entities(src)
        sstem = {stem(x) for x in sent}
        # also allow any word present in the source in any case form
        swords = {w.lower() for w in WORDRE.findall(src)}
        for e in sorted(entities(new)):
            if e in SOFT or e in sent or e in swords or stem(e) in sstem:
                continue
            bad.append(f"introduced a name not in the source: '{e}'")
            break
    if rules.get("no_scope_escalation", True):
        ts, tn = verb_tier(src), verb_tier(new)
        if tn > ts:
            names = {1: "contributor", 2: "doer", 3: "owner/leader"}
            bad.append(f"escalated the claim from {names.get(ts, ts)} "
                       f"to {names.get(tn, tn)}")
    return (not bad), bad


REWRITE_PROMPT = """Shorten this resume bullet to at most {budget} characters.

RULES — a violation makes the output unusable:
- Use ONLY facts present in the original. Add nothing.
- Do not introduce any number, tool, system, company, or team name that is
  not already in the original.
- Do not strengthen the claim. If it says "helped", it may not become "led".
  If it says "designed", it may not become "implemented".
- Keep the original's own vocabulary wherever possible.
- Return ONLY the shortened bullet. No preamble, no quotes, no explanation.

Job description context (for choosing WHICH facts to keep, never for adding facts):
{jd}

Original bullet:
{bullet}"""


def llm_rewrite(items, jd_text, cfg):
    """Returns {id: (new_text, accepted, reasons)}. Falls back silently to the
    deterministic trim on any failure — missing key, network, bad output."""
    rules = cfg.get("rewrite", {}).get("guardrails", {})
    model = cfg.get("rewrite", {}).get("model", "claude-sonnet-5")
    out = {}
    try:
        import anthropic
    except ImportError:
        print("  --llm needs the SDK:  pip install anthropic")
        return out
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("  --llm needs ANTHROPIC_API_KEY set in your environment")
        return out
    client = anthropic.Anthropic()
    jd_short = jd_text[:1800]
    for it in items:
        src, budget = it["text"], it["budget"]
        try:
            r = client.messages.create(
                model=model, max_tokens=300,
                messages=[{"role": "user", "content": REWRITE_PROMPT.format(
                    budget=budget, jd=jd_short, bullet=src)}])
            new = r.content[0].text.strip().strip('"').strip()
        except Exception as e:
            out[it["id"]] = (src, False, [f"model call failed: {type(e).__name__}"])
            continue
        ok, reasons = check_rewrite(src, new, rules)
        if ok and len(new) <= budget:
            out[it["id"]] = (new, True, [])
        else:
            out[it["id"]] = (src, False, reasons or ["still too long"])
    return out


# ------------------------------------------------------------------ select
def select(cfg, jobs, exps, jdw):
    page = cfg.get("page", {})
    cpl = page.get("chars_per_line", 110)
    maxlines = page.get("max_body_lines", 44)
    minscore = page.get("min_score", 1)

    mcfg = cfg.get("matching", {})
    scored = defaultdict(list)
    for e in exps:
        jid = e.get("job")
        if jid not in jobs or e.get("exclude"):
            continue
        band, raw, top = score(e, jdw, mcfg)
        if band < minscore and not e.get("pin"):
            continue
        scored[jid].append({"exp": e, "band": band, "raw": raw, "top": top,
                            "text": e["text"].get("long", "")})
    for jid in scored:
        scored[jid].sort(key=lambda x: (-x["band"], -x["raw"]))

    order = sorted(jobs.values(), key=lambda j: -j.get("priority", 0))
    used, chosen = 0, defaultdict(list)
    # Enough rounds for the greediest job — a fixed ceiling here would silently
    # cap max_bullets and the config would be quietly lying to you.
    rounds = max([j.get("max_bullets", 4) for j in jobs.values()] or [0])
    for rnd in range(rounds):                   # round-robin so senior jobs fill first
        progressed = False
        for j in order:
            jid = j["id"]
            cand = scored.get(jid, [])
            if rnd >= min(j.get("max_bullets", 4), len(cand)):
                continue
            item = cand[rnd]
            need = max(1, -(-len(item["text"]) // cpl))
            if used + need > maxlines:
                continue
            chosen[jid].append(item)
            used += need
            progressed = True
        if not progressed:
            break
    return chosen, scored, used, cpl, maxlines


def ats(chosen, jdw, jd_title, jobs):
    top = sorted(jdw, key=lambda x: -jdw[x])[:60]
    body = " ".join(i["out"] for v in chosen.values() for i in v)
    body += " " + " ".join(f"{j.get('role','')} {j.get('company','')}" for j in jobs.values())
    have = expand(set(toks(body)) | phrases(body))
    got = [t for t in top if t in have]
    miss = [t for t in top if t not in have]
    tt = set(toks(jd_title))
    tm = len(tt & have) / max(len(tt), 1)
    return round(100 * (0.75 * len(got) / max(len(top), 1) + 0.25 * tm)), miss, got


# -------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("jd")
    ap.add_argument("--llm", action="store_true",
                    help="let a model shorten bullets (guardrailed, reviewable)")
    a = ap.parse_args()

    jdp = a.jd if os.path.exists(a.jd) else os.path.join(ROOT, a.jd)
    if os.path.abspath(jdp).startswith(os.path.abspath(FORBIDDEN)):
        die("the build step must never read source/draft/")
    if not os.path.exists(jdp):
        die(f"JD not found: {a.jd}")

    jd_text = open(jdp, encoding="utf-8").read()
    name = os.path.splitext(os.path.basename(jdp))[0]
    jd_title = next((l.strip("# ").strip() for l in jd_text.splitlines() if l.strip()), name)

    cfg, jobs, exps, gated = load()
    if not exps:
        die("no confirmed experiences — set confirmed: true in data/experiences.yaml")

    jdw = jd_terms(jd_text)
    profile, sig, s_, e_, ratio = classify(jd_text, jd_title)
    chosen, scored, used, cpl, maxlines = select(cfg, jobs, exps, jdw)

    # fit each bullet to its line budget
    items = []
    for jid, lst in chosen.items():
        for it in lst:
            lines = max(1, -(-len(it["text"]) // cpl))
            it["budget"] = min(len(it["text"]), lines * cpl)
            it["out"] = it["text"]
            if len(it["text"]) > cpl * 2:              # over two lines: tighten
                it["budget"] = cpl * 2
                items.append({"id": it["exp"]["id"], "text": it["text"],
                              "budget": it["budget"], "ref": it})

    rewrites = {}
    rwcfg = cfg.get("rewrite") or {}
    if a.llm and rwcfg.get("enabled", True) and items:
        print(f"  rewriting {len(items)} long bullets via "
              f"{rwcfg.get('model', 'claude-sonnet-5')}…")
        rewrites = llm_rewrite(items, jd_text, cfg)
    for it in items:
        new, ok, why = rewrites.get(it["id"], (None, False, ["not attempted"]))
        it["ref"]["out"] = new if ok else trim(it["text"], it["budget"])
        it["ref"]["rewrite"] = (new, ok, why)

    scoreval, miss, got = ats(chosen, jdw, jd_title, jobs)

    # ------------------------------------------------------------- render
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(LIN, exist_ok=True)
    r = R.Renderer(cfg)
    shipped = []
    for sec in cfg.get("sections", []):
        if not sec.get("enabled", True):
            continue
        if sec["type"] == "header":
            r.header(cfg.get("identity", {}))
        elif sec["type"] == "text" and sec.get("body"):
            r.section_title(sec.get("title", ""))
            r.text_block(sec["body"])
        elif sec["type"] == "jobs":
            r.section_title(sec.get("title", "EXPERIENCE"))
            for j in sorted(jobs.values(), key=lambda x: -x.get("priority", 0)):
                lst = chosen.get(j["id"], [])
                if not lst:
                    continue
                outs = [i["out"] for i in lst]
                shipped += outs
                r.job_block(j, outs)
        elif sec["type"] == "tags":
            allowed = sec.get("items", [])
            if sec.get("verify_against_bullets"):
                blob = " ".join(shipped).lower()
                allowed = [t for t in allowed if t.lower() in blob]
            if allowed:
                r.section_title(sec.get("title", "SKILLS"))
                r.tags(allowed)

    dp = os.path.join(OUT, f"{name}.docx")
    r.save(dp)
    v = R.verify(dp, shipped)

    # PDF is opt-in: as of 2026 the major parsers still read .docx more
    # reliably, so the default output stays the one most likely to survive an
    # ATS. Ask for it in config when a human is the reader.
    ocfg = cfg.get("output") or {}
    pdf_path, pdf_err = None, None
    if "pdf" in [str(f).lower() for f in ocfg.get("formats", ["docx"])]:
        pdf_path, pdf_err = R.to_pdf(dp, ocfg.get("pdf_engine", "auto"))

    # -------------------------------------------------------------- files
    with open(os.path.join(OUT, f"{name}-gaps.md"), "w", encoding="utf-8") as f:
        f.write(f"# Gaps — {jd_title}\n\n")
        f.write(f"- profile: **{profile}** (seniority {sig}, strategy/execution {s_}/{e_})\n")
        f.write(f"- ATS score: **{scoreval}/100**\n")
        f.write(f"- bullets shipped: {len(shipped)} | experiences eligible: {len(exps)} "
                f"| gated out as unconfirmed: {gated}\n\n")
        if profile == "BELOW DIRECTOR":
            f.write("> **Seniority flag:** this posting reads below Director.\n\n")
        if scoreval < 70:
            f.write("## Below 70 — real coverage gaps\n\n"
                    "Nothing confirmed matches these. Either the experience is missing, "
                    "or it exists but you have not confirmed it yet.\n\n")
        f.write("## JD terms with no matching bullet\n\n")
        for t in miss[:40]:
            f.write(f"- {t} (weight {jdw[t]:.1f})\n")
        f.write("\n## Covered\n\n" + ", ".join(got[:40]) + "\n")

    if items:
        with open(os.path.join(OUT, f"{name}-rewrites.md"), "w", encoding="utf-8") as f:
            f.write(f"# Rewrites — {jd_title}\n\n")
            f.write("Every shortened bullet, original beside result. "
                    "**Read this before sending.**\n\n")
            for it in items:
                new, ok, why = it["ref"].get("rewrite", (None, False, []))
                f.write(f"### {it['id']}\n\n")
                f.write(f"- **original:** {it['text']}\n")
                f.write(f"- **shipped:**  {it['ref']['out']}\n")
                if ok:
                    f.write("- status: AI rewrite, passed all guardrails\n\n")
                else:
                    f.write(f"- status: trimmed deterministically — "
                            f"AI version rejected ({'; '.join(why)})\n\n")

    with open(os.path.join(LIN, f"{name}.md"), "w", encoding="utf-8") as f:
        f.write(f"# Lineage — {name}\n\n| # | id | job | tier | band | shipped |\n"
                "|---|---|---|---|---|---|\n")
        n = 0
        for jid, lst in chosen.items():
            for i in lst:
                n += 1
                e = i["exp"]
                f.write(f"| {n} | `{e['id']}` | {jid} | {e.get('tier','')} | "
                        f"{i['band']} | {i['out'][:70].replace('|', '/')}… |\n")

    ok_rw = sum(1 for i in items if i["ref"].get("rewrite", (0, False, 0))[1])
    print(f"profile   {profile}")
    print(f"bullets   {len(shipped)} shipped | {len(exps)} eligible | {gated} gated out")
    print(f"ATS       {scoreval}/100" + ("   <-- below 70" if scoreval < 70 else ""))
    print(f"lines     {used}/{maxlines}")
    if items:
        print(f"rewrites  {ok_rw}/{len(items)} AI-accepted, "
              f"{len(items)-ok_rw} fell back to trim")
    print(f"docx      {v['paragraphs']} paras, {v['tables']} tables, "
          f"{'all text extracts' if not v['missing'] else str(len(v['missing'])) + ' MISSING'}")
    print(f"\n  {dp}")
    if pdf_path:
        print(f"  {pdf_path}")
    elif pdf_err:
        print(f"  PDF not written — {pdf_err}")
    if items:
        print(f"  {os.path.join(OUT, name + '-rewrites.md')}   <-- review before sending")


if __name__ == "__main__":
    main()
