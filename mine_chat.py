"""
mine_chat.py — find forgotten work in your AI chat history.

    python mine_chat.py                       reads ./export
    python mine_chat.py --source path/to/dir  anywhere else
    python mine_chat.py --list                just show what it detects

Reads an export from ChatGPT, Claude, Gemini/Takeout, or any folder of
markdown or text files, and finds conversations that look like real work.

Produces CANDIDATES only. Nothing here is a verified claim. Everything is
written with `confirmed: false` and stays invisible to the resume builder
until you say otherwise.

Evidence grading — based on what YOU pasted, never on what the AI said:

  OPERATIONAL  you pasted output that only exists if a system ran: stack
               traces, error codes, API responses, result rows, log lines.
               Strongest evidence that something was real.
  CONFIGURED   you pasted code or config. Evidence of building, not running.
  DISCUSSED    the topic appears, no artifact. Exploration only.

Vocabulary comes from config/mining.yaml. EDIT THAT FILE FIRST — the
shipped defaults are for one profession and will find nothing in yours.
"""
import os, re, sys, json, glob, argparse, datetime, yaml
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, "work")
CFG = os.path.join(ROOT, "config", "mining.yaml")

# ------------------------------------------------------- artifact detectors
OPERATIONAL_PAT = [
    r"Traceback \(most recent call last\)",
    r"\b[A-Za-z_]*(Error|Exception)\b\s*:",
    r"\bSQL compilation error\b",
    r"\bstatus(?:_code)?[\"']?\s*[:=]\s*[2-5]\d{2}\b",
    r"^\s*\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}",
    r"\b\d+\s+rows?\s+(affected|returned|selected|inserted|updated)\b",
    r"\bRows?\s*:\s*\d+\b",
    r"\|\s*-{3,}\s*\|",
    r"\b(WARN|ERROR|INFO|DEBUG)\s+\[",
    r"\bexit (code|status) \d+\b",
    r"\bconnection (refused|timed out|reset)\b",
    r"\bpermission denied\b",
    r"\bdoes not exist or not authorized\b",
    r"\b\d+ (passed|failed|skipped)\b",
]
CONFIGURED_PAT = [
    r"\bCREATE\s+(OR\s+REPLACE\s+)?(TABLE|VIEW|TAG|MASKING POLICY|ROW ACCESS POLICY|SCHEMA|DATABASE|INDEX|FUNCTION|PROCEDURE)\b",
    r"\bALTER\s+(TABLE|TAG|SESSION|ACCOUNT|USER|ROLE)\b",
    r"\bGRANT\s+\w+.*\bON\b",
    r"\bSELECT\b[\s\S]{0,400}?\bFROM\b",
    r"^\s*apiVersion\s*:",
    r"^\s*(version|services|jobs|steps|on|resources|models)\s*:\s*$",
    r"\bdef\s+\w+\s*\(",
    r"^\s*(import|from)\s+\w+",
    r"\bfunction\s+\w+\s*\(",
    r"\bresource\s+\"\w+\"\s+\"\w+\"\s*\{",
    r"^\s*\{[\s\S]{0,200}?\"\w+\"\s*:",
    r"\{\{\s*(config|ref|source)\s*\(",
]
CODE_FENCE = re.compile(r"```")
NUM_PAT = re.compile(
    r"(?<![\w.])(\$?\d{1,3}(?:,\d{3})+|\$?\d+(?:\.\d+)?)\s*"
    r"(%|percent|k\b|m\b|million|billion|hours?|days?|weeks?|months?|years?|FTEs?|"
    r"rows?|records?|tables?|columns?|assets?|datasets?|sources?|domains?|stewards?|"
    r"users?|reports?|dashboards?|pipelines?|models?|policies|tags?|rules?|tickets?|"
    r"schemas?|databases?|systems?|applications?|apps?|teams?|people|headcount|clients?)",
    re.I)


SKIPPED = []   # files that could not be read — reported, never swallowed


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def load_json(fp):
    """Read a JSON export, trying the encodings exports actually ship with.

    Returns (data, None) or (None, reason). A file that cannot be parsed is
    reported rather than skipped in silence — "nothing qualified" must never be
    the only symptom of an export this tool simply failed to open.
    """
    problem = ""
    for enc in ("utf-8", "utf-8-sig", "utf-16"):
        try:
            with open(fp, encoding=enc) as fh:
                return json.load(fh), None
        except UnicodeError as e:
            problem = f"{type(e).__name__}: {e}"
        except Exception as e:
            return None, f"{type(e).__name__}: {e}"
    return None, problem or "could not decode"


def load_cfg():
    if not os.path.exists(CFG):
        sys.exit(f"ERROR: {CFG} not found. It defines what counts as work in your field.")
    return yaml.safe_load(open(CFG, encoding="utf-8")) or {}


# ═══════════════════════════════════════════════════ export format readers
# Each reader yields {title, created, messages:[{role, text}]}.

def read_chatgpt(files):
    """ChatGPT: array of conversations, each with a `mapping` of message nodes."""
    for fp in files:
        convs, err = load_json(fp)
        if err:
            SKIPPED.append((fp, err))
            continue
        if not isinstance(convs, list):
            continue
        for c in convs:
            if not isinstance(c, dict) or "mapping" not in c:
                continue
            msgs = []
            for node in (c.get("mapping") or {}).values():
                m = node.get("message")
                if not m:
                    continue
                role = ((m.get("author") or {}).get("role")) or ""
                cont = m.get("content") or {}
                parts = []
                for p in cont.get("parts") or []:
                    if isinstance(p, str):
                        parts.append(p)
                    elif isinstance(p, dict) and p.get("text"):
                        parts.append(p["text"])
                if parts:
                    msgs.append({"role": role, "text": "\n".join(parts)})
            if msgs:
                yield {"title": c.get("title") or "(untitled)",
                       "created": c.get("create_time") or 0, "messages": msgs}


def read_claude(files):
    """Claude: array of conversations with `chat_messages` [{sender, text}]."""
    for fp in files:
        convs, err = load_json(fp)
        if err:
            SKIPPED.append((fp, err))
            continue
        if not isinstance(convs, list):
            continue
        for c in convs:
            if not isinstance(c, dict) or "chat_messages" not in c:
                continue
            msgs = []
            for m in c.get("chat_messages") or []:
                txt = m.get("text") or ""
                if not txt:
                    for blk in m.get("content") or []:
                        if isinstance(blk, dict) and blk.get("text"):
                            txt += blk["text"] + "\n"
                if txt.strip():
                    role = "user" if m.get("sender") in ("human", "user") else "assistant"
                    msgs.append({"role": role, "text": txt})
            if msgs:
                yield {"title": c.get("name") or "(untitled)",
                       "created": c.get("created_at") or 0, "messages": msgs}


def read_generic_json(files):
    """Anything shaped like [{messages:[{role,content}]}] or [{role,content}]."""
    for fp in files:
        data, err = load_json(fp)
        if err:
            SKIPPED.append((fp, err))
            continue
        blocks = data if isinstance(data, list) else [data]
        for i, c in enumerate(blocks):
            if not isinstance(c, dict):
                continue
            raw = c.get("messages") or c.get("conversation") or c.get("turns")
            if not isinstance(raw, list):
                continue
            msgs = []
            for m in raw:
                if not isinstance(m, dict):
                    continue
                txt = m.get("content") or m.get("text") or ""
                if isinstance(txt, list):
                    txt = " ".join(x.get("text", "") for x in txt if isinstance(x, dict))
                if txt:
                    role = str(m.get("role") or m.get("sender") or "user").lower()
                    msgs.append({"role": "user" if role in ("user", "human") else "assistant",
                                 "text": str(txt)})
            if msgs:
                yield {"title": c.get("title") or c.get("name") or f"{os.path.basename(fp)} #{i+1}",
                       "created": c.get("created_at") or c.get("create_time") or 0,
                       "messages": msgs}


def read_claude_code(files):
    """Claude Code session transcripts (.jsonl) — already on your disk under
    ~/.claude/projects, no export request needed. `--pull-claude` copies them
    into ./export/claude-code first.

    Only text you typed becomes user evidence. Tool results, system reminders,
    and command output also arrive typed "user" in these files, so anything
    that opens with markup or a caveat header is discarded.
    """
    for fp in files:
        msgs, title = [], ""
        try:
            fh = open(fp, encoding="utf-8", errors="replace")
        except Exception as e:
            SKIPPED.append((fp, f"{type(e).__name__}: {e}"))
            continue
        created = ""
        with fh:
            for ln in fh:
                try:
                    o = json.loads(ln)
                except Exception:
                    continue
                t, msg = o.get("type"), o.get("message") or {}
                if t not in ("user", "assistant"):
                    continue
                if not created and o.get("timestamp"):
                    created = str(o["timestamp"])
                c = msg.get("content")
                texts = []
                if isinstance(c, str):
                    texts = [c]
                elif isinstance(c, list):
                    texts = [b.get("text", "") for b in c
                             if isinstance(b, dict) and b.get("type") == "text"]
                txt = "\n".join(x for x in texts if x).strip()
                if not txt:
                    continue
                if t == "user" and (txt.startswith(("<", "Caveat:")) or
                                    "system-reminder" in txt[:200]):
                    continue        # harness plumbing, not something you said
                msgs.append({"role": t, "text": txt})
                if t == "user" and not title:
                    title = norm(txt)[:70]
        if msgs:
            yield {"title": title or os.path.basename(fp),
                   "created": created[:10], "messages": msgs}


def pull_claude(dest):
    """Copy Claude Code transcripts from ~/.claude/projects into ./export.

    Sessions from THIS project are skipped: transcripts of building a resume
    tool are saturated with resume vocabulary, and mining them would be the
    resume agreeing with itself — the exact circularity the quarantine rules
    exist to stop.
    """
    src = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    if not os.path.isdir(src):
        sys.exit(f"ERROR: {src} not found — no Claude Code history on this machine.")
    os.makedirs(dest, exist_ok=True)
    copied = skipped_self = 0
    for fp in sorted(glob.glob(os.path.join(src, "*", "*.jsonl"))):
        if os.path.getsize(fp) < 2048:
            continue                       # empty or near-empty session
        head = open(fp, encoding="utf-8", errors="replace").read(20000)
        if re.search(r"resume[-_ ]?(agent|builder)|session-env", head, re.I):
            skipped_self += 1
            continue
        proj = os.path.basename(os.path.dirname(fp))
        out = os.path.join(dest, f"{proj}--{os.path.basename(fp)}")
        import shutil
        shutil.copy2(fp, out)
        copied += 1
    print(f"pulled {copied} session(s) into {dest}")
    print(f"skipped {skipped_self} resume-builder session(s) — mining those "
          f"would be the resume citing itself")
    return copied


def read_takeout(files):
    """Google Takeout "My Activity" JSON — how Gemini history actually arrives.

    Takeout records one activity per prompt, not one per conversation, so a
    day's prompts are grouped into a single entry. Only what you typed is in
    there, which is exactly what the grading wants.
    """
    for fp in files:
        recs, err = load_json(fp)
        if err:
            SKIPPED.append((fp, err))
            continue
        if not isinstance(recs, list):
            continue
        def is_ai(r):
            blob = " ".join([str(r.get("header") or "")] +
                            [str(x) for x in (r.get("products") or [])])
            return re.search(r"gemini|bard", blob, re.I)
        recs = [r for r in recs if isinstance(r, dict)]
        ai = [r for r in recs if is_ai(r)] or recs
        byday = defaultdict(list)
        for r in ai:
            t = re.sub(r"^\s*(Prompted|Asked|Used)\s+", "", str(r.get("title") or ""))
            if t.strip():
                byday[str(r.get("time") or "")[:10]].append(t.strip())
        for when, prompts in sorted(byday.items()):
            yield {"title": f"Gemini activity — {when or 'undated'}",
                   "created": when,
                   "messages": [{"role": "user", "text": "\n\n".join(prompts)}]}


def read_textfiles(files):
    """A folder of .md/.txt files — one file is one 'conversation'.

    Works for Gemini/Takeout exports converted to text, Obsidian notes, work
    journals, anything. Lines starting with '>' or 'You:' count as yours.
    """
    for fp in files:
        try:
            body = open(fp, encoding="utf-8", errors="replace").read()
        except Exception as e:
            SKIPPED.append((fp, f"{type(e).__name__}: {e}"))
            continue
        if not body.strip():
            continue
        mine, theirs = [], []
        for ln in body.splitlines():
            if re.match(r"^\s*(>|You:|Me:|User:|Human:|\*\*You\*\*|## You)", ln):
                mine.append(re.sub(r"^\s*(>|You:|Me:|User:|Human:|\*\*You\*\*|## You)\s*", "", ln))
            else:
                theirs.append(ln)
        msgs = []
        if mine:
            msgs.append({"role": "user", "text": "\n".join(mine)})
            msgs.append({"role": "assistant", "text": "\n".join(theirs)})
        else:
            # no speaker markers: treat the whole file as yours, which is the
            # safe reading for a journal or notes file
            msgs.append({"role": "user", "text": body})
        yield {"title": os.path.splitext(os.path.basename(fp))[0],
               "created": os.path.getmtime(fp), "messages": msgs}


def detect(source):
    """Work out which readers apply. Returns a list of (label, reader, files).

    A list, not a single winner: an export folder legitimately holds a ChatGPT
    export next to pulled Claude Code sessions next to a notes directory, and
    one run should mine all of it. Each .json file is sniffed individually so
    mixed folders sort correctly.
    """
    if os.path.isfile(source):
        if source.endswith(".jsonl"):
            return [("Claude Code", read_claude_code, [source])]
        jsonl, jsons, texts = ([], [source], []) if source.endswith(".json") \
            else ([], [], [source])
    else:
        jsonl = sorted(glob.glob(os.path.join(source, "**", "*.jsonl"), recursive=True))
        jsons = sorted(glob.glob(os.path.join(source, "**", "*.json"), recursive=True))
        texts = sorted(glob.glob(os.path.join(source, "**", "*.md"), recursive=True) +
                       glob.glob(os.path.join(source, "**", "*.txt"), recursive=True))
    buckets = defaultdict(list)
    for fp in jsons:
        try:
            with open(fp, encoding="utf-8") as fh:
                head = fh.read(6000)
        except Exception:
            head = ""
        if '"mapping"' in head:
            buckets["ChatGPT"].append(fp)
        elif '"chat_messages"' in head:
            buckets["Claude"].append(fp)
        elif '"titleUrl"' in head or '"products"' in head:
            buckets["Google Takeout"].append(fp)
        else:
            buckets["generic JSON"].append(fp)
    readers = {"ChatGPT": read_chatgpt, "Claude": read_claude,
               "Google Takeout": read_takeout, "generic JSON": read_generic_json}
    groups = [(lb, readers[lb], fps) for lb, fps in buckets.items() if fps]
    if jsonl:
        groups.append(("Claude Code", read_claude_code, jsonl))
    if texts:
        groups.append(("text/markdown files", read_textfiles, texts))
    return groups


def find_html(source):
    """Takeout's default download is MyActivity.html, which nothing here reads.
    Worth saying so out loud rather than reporting an empty result."""
    if os.path.isfile(source):
        return [source] if source.lower().endswith((".html", ".htm")) else []
    return sorted(glob.glob(os.path.join(source, "**", "*.html"), recursive=True) +
                  glob.glob(os.path.join(source, "**", "*.htm"), recursive=True))


# ═══════════════════════════════════════════════════════════════ analysis
def build_scorer(cfg):
    sc = cfg.get("scoring", {})
    tiers = [(cfg.get("core") or [], sc.get("core_weight", 3), True),
             (cfg.get("supporting") or [], sc.get("supporting_weight", 2), False),
             (cfg.get("ambient") or [], sc.get("ambient_weight", 1), None)]
    cap = sc.get("ambient_cap", 10)

    def score(text):
        low = text.lower()
        total, amb, core_hits, hits = 0, 0, set(), []
        for terms, w, is_core in tiers:
            for t in terms:
                n = low.count(str(t).lower())
                if not n:
                    continue
                hits.append((t, n))
                if is_core is None:
                    amb += min(n, 5)
                else:
                    total += w * min(n, 5)
                if is_core:
                    core_hits.add(t)
        return total + min(amb, cap), core_hits, hits
    return score


def grade(user_text):
    for p in OPERATIONAL_PAT:
        if re.search(p, user_text, re.I | re.M):
            return "OPERATIONAL", p
    for p in CONFIGURED_PAT:
        if re.search(p, user_text, re.I | re.M):
            return "CONFIGURED", p
    if CODE_FENCE.search(user_text):
        return "CONFIGURED", "fenced code block"
    return "DISCUSSED", ""


def excluded(title, body, cfg):
    tl = title.lower()
    for w in cfg.get("exclude_when_title_matches") or []:
        if re.search(rf"\b{re.escape(str(w))}\b", tl):
            return True
    ex = cfg.get("exclude_when_body_repeats") or {}
    ph, th = ex.get("phrases") or [], ex.get("threshold", 3)
    if ph and sum(body.lower().count(str(p)) for p in ph) >= th:
        return True
    return False


# ═══════════════════════════════════════════════════════ asserted claims
# The difference between "Create a masking policy" and "Created a masking
# policy" is the difference between an instruction you gave a model and work
# you did. Only the second is evidence, and it is quoted verbatim — this tool
# surfaces claims you already made. It never writes one for you.

SENT = re.compile(r"(?<=[.!?])\s+|\n+")
ASK = re.compile(
    r"^\s*(can|could|would|should|how|what|why|when|where|is|are|do|does|did|please|"
    r"help|give|generate|make|draft|explain|summari[sz]e|review|suggest|tell|show|"
    r"need|want|let'?s|write|create|add|use|set|update|select|alter|grant|insert)\b", re.I)
CODE = re.compile(r"[{}]|\b(SELECT|CREATE|ALTER|GRANT|INSERT|VALUES|WHERE|RETURNS|"
                  r"FROM|JOIN|def|import)\b")
FIRST_PERSON = re.compile(
    r"\b(?:i|we|my team|our team)\s+(?:also\s+|then\s+|later\s+|successfully\s+)?"
    r"([a-z]+)\b", re.I)
# "we need to mask PII" is intent, not delivery. A verb followed by "to" is
# something you were about to do.
INTENT = re.compile(r"^\s*to\b", re.I)

SHIPPED = {
    "OPERATIONAL": "you pasted output only a running system produces — strongest "
                   "sign it shipped",
    "CONFIGURED": "you pasted code or config — you built it; confirm it reached "
                  "production",
    "DISCUSSED": "described only, no artifact pasted — confirm whether this "
                 "shipped and how",
}


def past_verbs(cfg):
    """Verbs that mark a claim of delivered work.

    The scope ladder from the rewrite guardrail, plus `claim_verbs` from
    config. Deliberately an explicit list rather than a pattern: matching any
    word ending in "ed" reads "we need to mask PII" as a delivery claim,
    because "need" is "ne" + "ed". A tool whose whole purpose is refusing to
    invent claims cannot guess at grammar.
    """
    try:
        from tailor import VERB_TIER
        out = {p: t for t, vs in VERB_TIER.items() for _, p in vs}
    except Exception:
        out = {}
    for v in cfg.get("claim_verbs") or []:
        out.setdefault(str(v).lower(), 2)
    return out


def claims(text, vocab, ladder):
    """Sentences YOU typed that assert completed work. Returned verbatim.

    Two ways in, both requiring past tense:
      "I/we <past>"      a first-person claim — the pronoun makes it yours
      "<ladder past> …"  resume-bullet phrasing, restricted to known verbs so
                         a stray -ed adjective cannot open a sentence and pass

    Questions, instructions to the model, and pasted code are all rejected.
    """
    out, seen = [], set()
    # Chat exports carry invisible Unicode (zero-width spaces, BOMs, soft
    # hyphens). Shipped into a resume they survive copy-paste and can break
    # ATS keyword matching, so strip them before anything is quoted.
    text = re.sub("[\u200b-\u200f\u2060\ufeff\u00ad]", "", text or "")
    for s in SENT.split(text):
        s = re.sub(r"\s+", " ", s).strip(" -*#>•\t")
        if not (40 <= len(s) <= 320) or "?" in s or ASK.match(s) or CODE.search(s):
            continue
        low = s.lower()
        matched = [v for v in vocab if v in low]
        if not matched:
            continue
        verb, rung = None, 0
        m = FIRST_PERSON.search(s)
        if m and m.group(1).lower() in ladder and not INTENT.match(s[m.end():]):
            verb, rung = m.group(1).lower(), ladder[m.group(1).lower()]
        else:
            f = re.match(r"^([A-Za-z]+)", s)
            if f and f.group(1).lower() in ladder and not INTENT.match(s[f.end():]):
                verb, rung = f.group(1).lower(), ladder[f.group(1).lower()]
        if not verb:
            continue
        key = re.sub(r"[^a-z0-9]", "", low)[:70]
        if key in seen:
            continue
        seen.add(key)
        out.append({"text": s, "verb": verb, "rung": rung,
                    "terms": sorted(set(matched))[:6]})
    return out


def jd_vocab(path):
    """Phrases a posting actually asks for, used to aim the mining at a job."""
    txt = open(path, encoding="utf-8").read()
    # drop YAML front matter — req ids and salary are not vocabulary
    txt = re.sub(r"^---\s*\n.*?\n---\s*\n", "", txt, flags=re.S).lower()
    stop = set("""the and or of to in for a an with on at by from as is are be will can
    this that these those you your our their we they it its role position job team work
    including include etc via while within across also new using use used help ensure
    ensuring strong excellent experience years ability across other such more most""".split())
    words = re.findall(r"[a-z][a-z\-]+", txt)
    grams = defaultdict(int)
    for n in (2, 3):
        for i in range(len(words) - n + 1):
            g = words[i:i + n]
            if g[0] in stop or g[-1] in stop or any(len(w) < 3 for w in g):
                continue
            grams[" ".join(g)] += 1
    return sorted([g for g, n in grams.items() if n >= 2], key=lambda g: -grams[g])[:120]


def slug(s, n=5):
    w = [x for x in re.findall(r"[a-z]+", s.lower()) if len(x) > 3][:n]
    return "-".join(w) or "candidate"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=os.path.join(ROOT, "export"))
    ap.add_argument("--list", action="store_true", help="detect the format and stop")
    ap.add_argument("--jd", help="aim the mining at a posting: jd/<name>.md")
    ap.add_argument("--pull-claude", action="store_true",
                    help="copy Claude Code sessions from ~/.claude into ./export")
    a = ap.parse_args()

    if a.pull_claude:
        dest = os.path.join(ROOT, "export", "claude-code")
        if not pull_claude(dest):
            return
        a.source = dest

    if not os.path.exists(a.source):
        sys.exit(f"ERROR: no such source: {a.source}\n"
                 f"Put your AI export in ./export or pass --source <path>.")

    groups = detect(a.source)
    if not groups:
        html = find_html(a.source)
        if html:
            sys.exit(f"ERROR: found {len(html)} HTML file(s) and nothing else readable.\n"
                     f"Google Takeout defaults to MyActivity.html, which this tool does "
                     f"not parse.\nRe-run the Takeout export and choose JSON, then point "
                     f"--source at that folder.")
        sys.exit(f"ERROR: nothing readable in {a.source}\n"
                 f"Expected a .json export (ChatGPT, Claude, Takeout, generic), "
                 f"Claude Code .jsonl, or .md/.txt files.")
    for lb, _r, fps in groups:
        print(f"detected: {lb}  ({len(fps)} file(s))")
    label = " + ".join(lb for lb, _r, _f in groups)
    if a.list:
        return

    cfg = load_cfg()
    sc = cfg.get("scoring", {})
    scorer = build_scorer(cfg)
    min_core = sc.get("min_core_terms", 2)
    min_score = sc.get("min_score", 25)

    vocab = [str(t).lower() for t in
             (cfg.get("core") or []) + (cfg.get("supporting") or [])]
    jdterms = []
    if a.jd:
        jdp = a.jd if os.path.exists(a.jd) else os.path.join(ROOT, a.jd)
        if not os.path.exists(jdp):
            sys.exit(f"ERROR: JD not found: {a.jd}")
        jdterms = jd_vocab(jdp)
        vocab = sorted(set(vocab) | set(jdterms))
        print(f"aimed at   {os.path.basename(jdp)}  ({len(jdterms)} posting phrases)")
    ladder = past_verbs(cfg)

    os.makedirs(WORK, exist_ok=True)
    rows, dropped, quarantined = [], 0, 0

    def all_convs():
        for _lb, reader, files in groups:
            yield from reader(files)

    for conv in all_convs():
        msgs = conv["messages"]
        full = "\n\n".join(m["text"] for m in msgs)
        mine = "\n\n".join(m["text"] for m in msgs if m["role"] == "user")
        if not full.strip():
            continue
        title = norm(conv["title"])
        if excluded(title, full, cfg):
            quarantined += 1
            continue
        total, core, hits = scorer(full)
        found = claims(mine, vocab, ladder)
        # A sentence where you say you did the work is evidence in its own
        # right. Dropping it for failing a vocabulary threshold discards the
        # very thing this tool exists to surface.
        if (len(core) < min_core or total < min_score) and not found:
            dropped += 1
            continue
        g, why = grade(mine)
        ts = conv.get("created") or 0
        try:
            when = (datetime.date.fromtimestamp(float(ts)).isoformat() if ts
                    else "")
        except Exception:
            when = str(ts)[:10]
        nums = []
        for m in list(NUM_PAT.finditer(mine))[:6]:
            s = max(0, m.start() - 90)
            nums.append({"value": norm(m.group(0)),
                         "kind": "unknown",
                         "context": norm(mine[s:m.end() + 60])[:180]})
        rows.append({"title": title, "date": when, "score": total, "grade": g,
                     "why": why, "core": sorted(core), "numbers": nums,
                     "claims": found, "excerpt": norm(mine)[:400]})

    order = {"OPERATIONAL": 0, "CONFIGURED": 1, "DISCUSSED": 2}
    rows.sort(key=lambda r: (order[r["grade"]], -r["score"]))

    # ---------------------------------------------------- candidate YAML
    cand, used_ids = [], defaultdict(int)
    for r in rows:
        # One candidate per claim you made, not one per conversation. A single
        # conversation often covers several distinct pieces of work, and a
        # conversation with no claim in it is not an experience.
        for c in sorted(r["claims"], key=lambda x: -x["rung"])[:4]:
            # Similar titles slug to the same string. Two experiences sharing
            # an id would silently collapse into one in experiences.yaml.
            base = f"mined-{slug(c['text'])}"
            used_ids[base] += 1
            cand.append({
                "id": base if used_ids[base] == 1 else f"{base}-{used_ids[base]}",
                "job": "TODO",
                "confirmed": False,
                "tier": "chat-corroborated",
                "tags": (c["terms"] or r["core"])[:6],
                "metrics": r["numbers"][:3],
                # YOUR sentence, verbatim. Edit it into resume wording; do not
                # treat it as already written.
                "text": {"long": c["text"], "medium": "", "short": ""},
                "_evidence": {
                    "conversation": r["title"],
                    "date": r["date"],
                    "grade": r["grade"],
                    "shipped": SHIPPED.get(r["grade"], ""),
                    "your_words": c["text"],
                    "claim_verb": c["verb"],
                },
            })
    # One output pair per source, so mining a different --source can never
    # silently overwrite what you mined from your main export last month. The
    # default ./export (whatever mix it holds) keeps the canonical filename.
    if os.path.abspath(a.source) == os.path.abspath(os.path.join(ROOT, "export")):
        suffix = ""
    else:
        tag = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        suffix = f"-{tag}"
    cp = os.path.join(WORK, f"mined-candidates{suffix}.yaml")
    with open(cp, "w", encoding="utf-8") as f:
        f.write("# Candidates mined from your AI chat history.\n"
                "# text.long is a sentence YOU typed, quoted verbatim. Nothing here\n"
                "# was written for you — this is a claim you already made, surfaced\n"
                "# so you can decide whether it is true and whether it shipped.\n"
                "#\n"
                "# _evidence.shipped says how strong the proof of delivery is.\n"
                "# OPERATIONAL means something ran; it does not prove you were the\n"
                "# one who shipped it rather than the one evaluating it.\n"
                "#\n"
                "# For each: set a `job:`, rewrite text.long into resume wording,\n"
                "# then move it into data/experiences.yaml. All are confirmed: false\n"
                "# — the builder cannot see them until you say so.\n\n")
        yaml.safe_dump({"experiences": cand}, f, sort_keys=False,
                       allow_unicode=True, width=100)

    ip = os.path.join(WORK, f"mined-index{suffix}.md")
    with open(ip, "w", encoding="utf-8") as f:
        f.write(f"# Mined from {label} — CANDIDATES, NOT VERIFIED\n\n")
        f.write("Grade reflects artifacts in **your own** messages.\n")
        f.write("OPERATIONAL means you pasted output from something that ran — it "
                "still does not prove *you* delivered it rather than evaluated it.\n\n")
        f.write("| date | score | grade | conversation | numbers |\n|---|---|---|---|---|\n")
        for r in rows:
            f.write(f"| {r['date']} | {r['score']} | {r['grade']} | "
                    f"{r['title'][:60]} | {len(r['numbers'])} |\n")

    byg = defaultdict(int)
    for r in rows:
        byg[r["grade"]] += 1
    print(f"qualified {len(rows)}  (dropped {dropped} below threshold, "
          f"{quarantined} excluded as resume-writing)")
    print(f"grades    {dict(byg)}")
    print(f"numbers   {sum(len(r['numbers']) for r in rows)} you typed yourself")
    print(f"\n  {cp}\n  {ip}")
    if SKIPPED:
        print(f"\nWARNING: {len(SKIPPED)} file(s) could not be read and were not mined:")
        for fp, why in SKIPPED[:5]:
            print(f"  {os.path.basename(fp)} — {why}")
        if len(SKIPPED) > 5:
            print(f"  …and {len(SKIPPED) - 5} more")
    if not rows:
        print("\nNothing qualified." + (
            " Fix the unreadable file(s) above first." if SKIPPED else
            " If this is not your field, edit config/mining.yaml —\n"
            "the shipped vocabulary is for data governance."))


if __name__ == "__main__":
    main()
