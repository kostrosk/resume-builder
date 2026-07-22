"""
create_experiences.py — turn chat evidence into draft experience bullets.

    python create_experiences.py --jd jd/acme.md
    python create_experiences.py --jd jd/acme.md --llm   # synthesize prose

This is the step between mining and confirming. mine_chat.py finds the
conversations and pulls the sentences you typed; this clusters that evidence
into coherent units of work and drafts ONE experience per unit — grounded in
what you actually did, never invented.

Two modes, same guarantee:
  default   emits an evidence packet per work-theme: your own artifact-bearing
            sentences, grouped, for you (or an agent) to write the bullet from.
  --llm     a model drafts the bullet from that packet, then check_rewrite()
            rejects any draft that adds a number, tool, or scope not in the
            evidence. A rejected draft falls back to the packet.

Everything written is confirmed: false, tier: chat-created, with the source
conversations recorded. Nothing reaches a resume until you confirm it.
"""
import os, re, sys, argparse, yaml
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mine_chat as M
import tailor as T

ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, "work")
OUT = os.path.join(WORK, "created-experiences.yaml")


def theme_of(claim_terms, jd_terms):
    """The strongest shared vocabulary a claim belongs to — its work-theme."""
    hits = [t for t in claim_terms if t]
    return hits[0] if hits else "general"


def cluster(rows, cfg, jd_vocab):
    """Group claims across conversations into work-themes by shared core terms."""
    core = [str(t).lower() for t in (cfg.get("core") or [])]
    buckets = defaultdict(list)
    for r in rows:
        for c in r["claims"]:
            # a claim's theme is its highest-tier core term, else its first tag
            key = next((t for t in core if t in c["text"].lower()),
                       (c["terms"][0] if c["terms"] else "general"))
            buckets[key].append({**c, "title": r["title"], "date": r["date"]})
    # keep themes with real weight (>=2 distinct conversations of evidence)
    return {k: v for k, v in buckets.items()
            if len({c["title"] for c in v}) >= 2}


def llm_draft(theme, evidence, cfg):
    """Draft one bullet from the evidence packet; guardrail-check it."""
    try:
        import anthropic
    except ImportError:
        return None, "no SDK"
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None, "no key"
    facts = "\n".join(f"- {e['text']}" for e in evidence[:12])
    prompt = (
        f"These are sentences a data professional typed while doing work on "
        f"'{theme}'. Write ONE resume bullet, past tense, that captures what "
        f"they did. Use ONLY facts present below — invent no number, tool, "
        f"company, or scope. Be elegant and specific. Return only the bullet.\n\n"
        f"{facts}")
    try:
        client = anthropic.Anthropic()
        m = client.messages.create(model=cfg.get("rewrite", {}).get("model", "claude-sonnet-5"),
                                   max_tokens=220,
                                   messages=[{"role": "user", "content": prompt}])
        draft = m.content[0].text.strip().strip('"')
    except Exception as e:
        return None, f"{type(e).__name__}"
    # verify the draft invented nothing vs the concatenated evidence
    src = " ".join(e["text"] for e in evidence)
    rules = {k: v for k, v in cfg.get("rewrite", {}).get("guardrails", {}).items()
             if k != "max_length_ratio"}
    ok, why = T.check_rewrite(src, draft, rules)
    return (draft, "ok") if ok else (None, "; ".join(why))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=os.path.join(ROOT, "export"))
    ap.add_argument("--jd", help="theme and prioritize toward a posting")
    ap.add_argument("--llm", action="store_true", help="draft prose from evidence")
    a = ap.parse_args()

    if not os.path.exists(a.source):
        sys.exit(f"ERROR: no export at {a.source}")
    groups = M.detect(a.source)
    if not groups:
        sys.exit(f"ERROR: nothing readable in {a.source}")
    cfg_m = M.load_cfg()
    scorer = M.build_scorer(cfg_m)
    ladder = M.past_verbs(cfg_m)
    sc = cfg_m.get("scoring", {})
    vocab = [str(t).lower() for t in (cfg_m.get("core") or []) + (cfg_m.get("supporting") or [])]
    jd_vocab = []
    if a.jd:
        jdp = a.jd if os.path.exists(a.jd) else os.path.join(ROOT, a.jd)
        jd_vocab = M.jd_vocab(jdp)
        vocab = sorted(set(vocab) | set(jd_vocab))

    # gather qualified conversations with their asserted claims
    rows = []
    for lb, reader, files in groups:
        for conv in reader(files):
            mine = "\n\n".join(m["text"] for m in conv["messages"] if m["role"] == "user")
            full = "\n\n".join(m["text"] for m in conv["messages"])
            if not mine.strip() or M.excluded(M.norm(conv["title"]), full, cfg_m):
                continue
            claims = M.claims(mine, vocab, ladder)
            if not claims:
                continue
            ts = conv.get("created") or ""
            rows.append({"title": M.norm(conv["title"]), "date": str(ts)[:10],
                         "claims": claims})

    themes = cluster(rows, cfg_m, jd_vocab)
    order = jd_vocab or list(themes)
    themes = dict(sorted(themes.items(),
                         key=lambda kv: (order.index(kv[0]) if kv[0] in order else 999,
                                         -len(kv[1]))))

    cfg_r = {}
    cfp = os.path.join(ROOT, "config", "resume-config.yaml")
    if a.llm and os.path.exists(cfp):
        cfg_r = yaml.safe_load(open(cfp, encoding="utf-8")) or {}

    created = []
    for theme, evidence in themes.items():
        # dedupe near-identical sentences within a theme
        seen, uniq = set(), []
        for e in sorted(evidence, key=lambda x: -x["rung"]):
            k = re.sub(r"[^a-z0-9]", "", e["text"].lower())[:60]
            if k not in seen:
                seen.add(k)
                uniq.append(e)
        draft, note = (None, "packet")
        if a.llm:
            draft, note = llm_draft(theme, uniq, cfg_r)
        slug = "chat-" + re.sub(r"[^a-z0-9]+", "-", theme.lower()).strip("-")
        created.append({
            "id": slug, "job": "TODO", "confirmed": False, "tier": "chat-created",
            "tags": sorted({t for e in uniq for t in e["terms"]})[:6],
            "metrics": [],
            "text": {"long": draft or f"SYNTHESIZE from the evidence below "
                     f"({len(uniq)} claims across {len({e['title'] for e in uniq})} "
                     f"conversations).", "medium": "", "short": ""},
            "_evidence": {"theme": theme, "draft_status": note,
                          "conversations": sorted({e["title"] for e in uniq})[:6],
                          "your_words": [e["text"] for e in uniq[:8]]},
        })

    os.makedirs(WORK, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("# Draft experiences created from your chat evidence.\n"
                "# Each is grounded in sentences YOU typed (see _evidence.your_words).\n"
                "# Write/confirm text.long, set a job:, move the true ones into\n"
                "# data/experiences.yaml. All confirmed: false until you say so.\n\n")
        yaml.safe_dump({"experiences": created}, f, sort_keys=False,
                       allow_unicode=True, width=100)

    print(f"themes found   {len(themes)}")
    print(f"experiences    {len(created)} drafted ({'llm' if a.llm else 'evidence-packet'})")
    for c in created[:12]:
        ev = c["_evidence"]
        print(f"  [{ev['theme'][:26]:26}] {len(ev['your_words'])} claims / "
              f"{len(ev['conversations'])} convs")
    print(f"\n  {OUT}")


if __name__ == "__main__":
    main()
