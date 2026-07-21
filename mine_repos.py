"""
mine_repos.py — surface project evidence from local git repos and agent notes.

    python mine_repos.py                          scan the default roots
    python mine_repos.py --root path/to/projects  scan any folder of repos
    python mine_repos.py --agent-notes            include IDE agent walkthroughs

Default roots cover the Antigravity IDE workspace (~/.gemini/antigravity):
its scratch/ projects are git repos, and its brain/ holds per-session
walkthrough notes describing what was built.

PROVENANCE WARNING, and why it is printed on every candidate: README files
and agent walkthroughs are usually model-written. A sentence from them is a
lead to verify, not your words. That is one tier weaker than chat mining,
where the sentence is something you personally typed. Everything lands
`confirmed: false`, and the builder cannot see any of it until you rewrite
it in your own words and confirm it.
"""
import os, re, sys, glob, argparse, subprocess, yaml
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, "work")
CFG = os.path.join(ROOT, "config", "mining.yaml")
HOME = os.path.expanduser("~")
DEFAULT_ROOTS = [os.path.join(HOME, ".gemini", "antigravity", "scratch")]
BRAIN = os.path.join(HOME, ".gemini", "antigravity", "brain")


def load_cfg():
    if not os.path.exists(CFG):
        sys.exit(f"ERROR: {CFG} not found.")
    return yaml.safe_load(open(CFG, encoding="utf-8")) or {}


def git(repo, *args):
    try:
        r = subprocess.run(["git", "-C", repo, *args], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=30)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def vocab_hits(text, vocab):
    low = (text or "").lower()
    return sorted({v for v in vocab if v in low})


def first_sentences(md, n=3):
    """Opening prose of a README — its own description of the project."""
    body = re.sub(r"```.*?```", " ", md or "", flags=re.S)
    body = re.sub(r"^#.*$", " ", body, flags=re.M)
    body = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", body)
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", body))
             if 30 <= len(s.strip()) <= 300]
    return sents[:n]


def scan_repo(path, vocab):
    name = os.path.basename(path.rstrip("/\\"))
    readme = ""
    for cand in ("README.md", "readme.md", "README.txt"):
        p = os.path.join(path, cand)
        if os.path.exists(p):
            readme = open(p, encoding="utf-8", errors="replace").read()
            break
    commits = git(path, "rev-list", "--count", "HEAD")
    first = git(path, "log", "--reverse", "--format=%as", "-1")
    last = git(path, "log", "-1", "--format=%as")
    langs = defaultdict(int)
    for f in glob.glob(os.path.join(path, "**", "*.*"), recursive=True):
        ext = os.path.splitext(f)[1].lower()
        if ext in (".py", ".sql", ".ps1", ".js", ".ts", ".yaml", ".yml", ".sh", ".md"):
            langs[ext.lstrip(".")] += 1
    hits = vocab_hits(readme + " " + name.replace("-", " "), vocab)
    return {"name": name, "path": path, "readme": readme,
            "sentences": first_sentences(readme),
            "commits": commits or "0", "first": first, "last": last,
            "langs": sorted(langs, key=lambda k: -langs[k])[:4], "hits": hits}


def scan_brain(vocab, ladder):
    """Claim sentences inside Antigravity walkthrough notes.

    These are the agent's session summaries — 'we implemented X' written by
    the model that helped. Quoted verbatim as leads; tier agent-log.
    """
    from mine_chat import claims
    out = []
    for fp in sorted(glob.glob(os.path.join(BRAIN, "*", "walkthrough.md"))):
        txt = open(fp, encoding="utf-8", errors="replace").read()
        if re.search(r"resume|\bcv\b|cover letter", txt[:2000], re.I):
            continue                      # this tool's own sessions: circular
        for c in claims(txt, vocab, ladder):
            out.append({"src": os.path.basename(os.path.dirname(fp)), **c})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", default=[],
                    help="folder containing git repos (repeatable)")
    ap.add_argument("--agent-notes", action="store_true",
                    help="also mine IDE agent walkthrough notes (weakest tier)")
    a = ap.parse_args()

    cfg = load_cfg()
    vocab = [str(t).lower() for t in
             (cfg.get("core") or []) + (cfg.get("supporting") or []) +
             (cfg.get("ambient") or [])]
    roots = [r for r in (a.root or DEFAULT_ROOTS) if os.path.isdir(r)]
    if not roots and not a.agent_notes:
        sys.exit("ERROR: no scannable roots. Pass --root <folder-of-repos>.")

    repos = []
    for root in roots:
        for d in sorted(glob.glob(os.path.join(root, "*"))):
            if os.path.isdir(os.path.join(d, ".git")):
                repos.append(scan_repo(d, vocab))

    cand, used = [], defaultdict(int)

    def add(idbase, entry):
        used[idbase] += 1
        entry["id"] = idbase if used[idbase] == 1 else f"{idbase}-{used[idbase]}"
        cand.append(entry)

    for r in repos:
        quote = r["sentences"][0] if r["sentences"] else ""
        base = "repo-" + re.sub(r"[^a-z0-9]+", "-", r["name"].lower()).strip("-")
        add(base, {
            "id": "", "job": "TODO", "confirmed": False, "tier": "repo",
            "tags": (r["hits"] or ["portfolio"])[:6], "metrics": [],
            # the README's own description, quoted — rewrite it in YOUR words
            "text": {"long": quote or f"{r['name']}: no README description found.",
                     "medium": "", "short": ""},
            "_evidence": {
                "repo": r["path"], "commits": r["commits"],
                "active": f"{r['first']} to {r['last']}".strip(),
                "languages": r["langs"],
                "vocabulary": r["hits"],
                "shipped": "a git repo with commit history — the code exists; "
                           "confirm what it does, whether it ran, and that no "
                           "employer code is inside before citing it",
                "warning": "README text is usually model-written. This quote "
                           "is a lead, not your claim.",
            },
        })

    if a.agent_notes:
        try:
            from mine_chat import past_verbs
            ladder = past_verbs(cfg)
        except Exception:
            ladder = {}
        for c in scan_brain(vocab, ladder):
            base = "agent-" + re.sub(r"[^a-z0-9]+", "-",
                                     " ".join(c["text"].lower().split()[:5])).strip("-")
            add(base, {
                "id": "", "job": "TODO", "confirmed": False, "tier": "agent-log",
                "tags": c["terms"][:6], "metrics": [],
                "text": {"long": c["text"], "medium": "", "short": ""},
                "_evidence": {
                    "session": c["src"], "claim_verb": c["verb"],
                    "shipped": "written by an AI agent summarising a session in "
                               "your IDE. It describes work done with you, in "
                               "its voice — verify it happened, then rewrite "
                               "in your own words.",
                },
            })

    os.makedirs(WORK, exist_ok=True)
    out = os.path.join(WORK, "mined-repos.yaml")
    with open(out, "w", encoding="utf-8") as f:
        f.write("# Project evidence from local git repos"
                + (" and IDE agent notes" if a.agent_notes else "") + ".\n"
                "# READMEs and agent walkthroughs are usually MODEL-WRITTEN —\n"
                "# every text.long here is a lead to verify, not your words.\n"
                "# Rewrite in your own words, set a job:, then move the true\n"
                "# ones into data/experiences.yaml. All confirmed: false.\n\n")
        yaml.safe_dump({"experiences": cand}, f, sort_keys=False,
                       allow_unicode=True, width=100)

    print(f"repos      {len(repos)}")
    for r in repos:
        mark = "governance-relevant" if r["hits"] else "unrelated to vocabulary"
        print(f"  {r['name'][:44]:46} {r['commits']:>4} commits  {mark}")
    if a.agent_notes:
        n = sum(1 for c in cand if c['tier'] == 'agent-log')
        print(f"agent-log  {n} claim sentence(s) from walkthrough notes")
    print(f"candidates {len(cand)}\n\n  {out}")


if __name__ == "__main__":
    main()
