"""
mine_chat.py — evidence-graded extraction of data governance work from a
ChatGPT export.

Produces CANDIDATE evidence only. Nothing this script emits is a verified
claim. Grades reflect what artifacts appear in the USER's own messages,
never what the assistant said, and never an assumption of delivery.

Grades:
  OPERATIONAL  user pasted output that only exists if a system ran
               (stack traces, error codes, API/JSON responses, result rows,
               log lines). Strong delivery evidence.
  CONFIGURED   user pasted code or config (SQL DDL, YAML, JSON, Python,
               Terraform). Evidence of building, not of running.
  DISCUSSED    governance topic present, no artifact. Exploration only.

Numbers are harvested ONLY from user-authored text, and are emitted as
questions, never as confirmed metrics.
"""

import json, re, os, glob, datetime, html
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
EXPORT = os.path.join(ROOT, "export")
WORK = os.path.join(ROOT, "work")
os.makedirs(WORK, exist_ok=True)

# ---------------------------------------------------------------- keywords
# Weighted governance vocabulary, drawn from GOAL.md step 2 rubric.
GOV_TERMS = {
    3: [
        "data governance", "governance council", "data steward", "stewardship",
        "data catalog", "business glossary", "metadata repository",
        "openmetadata", "collibra", "alation", "purview", "data.world",
        "policy-as-code", "policy as code", "masking policy", "data contract",
        "classification policy", "data classification", "access control",
        "audit trail", "data lineage", "lineage", "rbac", "row access policy",
        "column-level security", "data quality framework", "dama", "dcam",
        "records retention", "retention policy", "data domain", "data owner",
        "human-in-the-loop", "agentic governance", "ai governance",
        "model governance", "responsible ai",
    ],
    2: [
        "pii", "phi", "gdpr", "ccpa", "sox", "hipaa", "dlp", "mdm",
        "master data", "data quality", "taxonomy", "ontology", "semantic layer",
        "metadata", "data dictionary", "schema registry", "data mesh",
        "data product", "snowflake tag", "tagging", "masking", "anonymiz",
        "pseudonymiz", "entitlement", "provisioning", "data privacy",
        "compliance", "regulatory", "certification", "attestation",
    ],
    1: [
        "snowflake", "dbt", "power bi", "tableau", "airflow", "fivetran",
        "databricks", "redshift", "bigquery", "sql server", "etl", "elt",
        "pipeline", "warehouse", "data model", "dimensional",
    ],
}

# ------------------------------------------------------- artifact detectors
# OPERATIONAL: output that implies something actually executed.
OPERATIONAL_PAT = [
    r"Traceback \(most recent call last\)",
    r"\b[A-Za-z_]*(Error|Exception)\b\s*:",
    r"\bSQL compilation error\b",
    r"\b(HTTP/1\.[01]|status(?:_code)?[\"']?\s*[:=]\s*)([2-5]\d{2})\b",
    r"^\s*\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}",          # log timestamps
    r"\b\d+\s+rows?\s+(affected|returned|selected|inserted|updated)\b",
    r"\bRows?\s*:\s*\d+\b",
    r"\|\s*-{3,}\s*\|",                                       # md result table
    r"\b(WARN|ERROR|INFO|DEBUG)\s+\[",
    r"\bexit (code|status) \d+\b",
    r"\bconnection (refused|timed out|reset)\b",
    r"\bpermission denied\b",
    r"\bDoes not exist or not authorized\b",
]
# CONFIGURED: code / config the user wrote or pasted.
CONFIGURED_PAT = [
    r"\bCREATE\s+(OR\s+REPLACE\s+)?(TABLE|VIEW|TAG|MASKING POLICY|ROW ACCESS POLICY|SCHEMA|DATABASE|WAREHOUSE|STREAM|TASK|FUNCTION)\b",
    r"\bALTER\s+(TABLE|TAG|SESSION|ACCOUNT|USER|ROLE)\b",
    r"\bGRANT\s+\w+.*\bON\b",
    r"\bSELECT\b[\s\S]{0,400}?\bFROM\b",
    r"^\s*apiVersion\s*:",
    r"^\s*(version|services|jobs|steps|on|resources)\s*:\s*$",
    r"\bdef\s+\w+\s*\(",
    r"^\s*(import|from)\s+\w+",
    r"\bresource\s+\"\w+\"\s+\"\w+\"\s*\{",
    r"^\s*\{[\s\S]{0,200}?\"\w+\"\s*:",
    r"\{\{\s*(config|ref|source)\s*\(",                        # dbt jinja
    r"\bmodels:\s*$",
]

CODE_FENCE = re.compile(r"```")

NUM_PAT = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*"
    r"(%|percent|k\b|m\b|million|billion|hours?|days?|weeks?|months?|years?|FTEs?|"
    r"rows?|records?|tables?|columns?|assets?|datasets?|sources?|domains?|stewards?|"
    r"users?|reports?|dashboards?|pipelines?|models?|policies|tags?|rules?|"
    r"schemas?|databases?|systems?|applications?|apps?|teams?|people|headcount)",
    re.I,
)
MONEY_PAT = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?\s*(?:[KMB]|million|billion)?", re.I)


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def msg_text(msg):
    """Extract plain text from a ChatGPT export message node."""
    if not msg:
        return ""
    c = msg.get("content") or {}
    ct = c.get("content_type")
    out = []
    if ct in ("text", "code", "execution_output"):
        for p in c.get("parts") or []:
            if isinstance(p, str):
                out.append(p)
    elif ct == "multimodal_text":
        for p in c.get("parts") or []:
            if isinstance(p, str):
                out.append(p)
            elif isinstance(p, dict) and p.get("text"):
                out.append(p["text"])
    else:
        for p in c.get("parts") or []:
            if isinstance(p, str):
                out.append(p)
    return "\n".join(out)


def grade(user_text):
    for pat in OPERATIONAL_PAT:
        if re.search(pat, user_text, re.I | re.M):
            return "OPERATIONAL", pat
    for pat in CONFIGURED_PAT:
        if re.search(pat, user_text, re.I | re.M):
            return "CONFIGURED", pat
    if CODE_FENCE.search(user_text):
        return "CONFIGURED", "fenced code block"
    return "DISCUSSED", ""


def score_terms(text):
    """Tier-1 terms are ambient tech vocabulary and cannot carry a conversation
    on their own; their contribution is capped. Core governance vocabulary
    (tier 3) must be present and repeated for a conversation to qualify."""
    low = text.lower()
    hits, total, t1_total = defaultdict(list), 0, 0
    t3_distinct = set()
    for w, terms in GOV_TERMS.items():
        for t in terms:
            n = low.count(t)
            if n:
                hits[w].append((t, n))
                if w == 1:
                    t1_total += min(n, 5)
                else:
                    total += w * min(n, 5)
                if w == 3:
                    t3_distinct.add(t)
    total += min(t1_total, 10)          # tier-1 cannot exceed 10 points
    return total, hits, t3_distinct


def excerpts(text, hits, limit=5):
    low, out, seen = text.lower(), [], set()
    terms = [t for w in (3, 2) for t, _ in hits.get(w, [])]
    for t in terms:
        i = low.find(t)
        if i < 0:
            continue
        a, b = max(0, i - 140), min(len(text), i + 200)
        frag = norm(text[a:b])
        key = frag[:60]
        if key in seen:
            continue
        seen.add(key)
        out.append((t, frag))
        if len(out) >= limit:
            break
    return out


# ------------------------------------------------------------------- parse
rows, dropped, quarantined = [], [], []
files = sorted(glob.glob(os.path.join(EXPORT, "conversations-*.json")))
print(f"parsing {len(files)} export parts...")

for fp in files:
    with open(fp, "r", encoding="utf-8") as fh:
        convs = json.load(fh)
    print(f"  {os.path.basename(fp)}: {len(convs)} conversations")
    for conv in convs:
        mapping = conv.get("mapping") or {}
        user_parts, all_parts = [], []
        for node in mapping.values():
            m = node.get("message")
            if not m:
                continue
            role = ((m.get("author") or {}).get("role")) or ""
            t = msg_text(m)
            if not t:
                continue
            all_parts.append(t)
            if role == "user":
                user_parts.append(t)
        if not all_parts:
            continue
        user_text = "\n\n".join(user_parts)
        full_text = "\n\n".join(all_parts)

        r_title = norm(conv.get("title") or "(untitled)")
        total, hits, t3 = score_terms(full_text)
        # Qualify only on sustained core-governance vocabulary. A single
        # passing mention, or ambient tech terms alone, is not evidence.
        if len(t3) < 2 or total < 25:
            dropped.append((norm(conv.get("title") or ""), total, len(t3)))
            continue

        # CIRCULAR PROVENANCE GUARD ------------------------------------
        # Conversations where the user was drafting a resume/CV/cover letter
        # score high on governance vocabulary because the *resume* contains
        # that vocabulary. Admitting them as corroboration would recycle
        # prior model-written claims back in as independent evidence.
        # Quarantine, never qualify.
        tl = r_title.lower()
        bl = full_text.lower()
        if (re.search(r"\b(resume|cv|cover letter|ats|job posting|job description|"
                      r"interview|linkedin profile|recruiter|salary)\b", tl)
                or sum(bl.count(k) for k in
                       ("my resume", "my cv", "cover letter", "hiring manager",
                        "bullet point", "job posting", "this posting",
                        "tailor my", "rewrite my")) >= 3):
            quarantined.append((r_title, total, len(t3)))
            continue

        g, why = grade(user_text)
        ct = conv.get("create_time") or 0
        ut = conv.get("update_time") or 0
        rows.append({
            "t3": sorted(t3),
            "id": conv.get("conversation_id", ""),
            "title": norm(conv.get("title") or "(untitled)"),
            "created": datetime.date.fromtimestamp(ct).isoformat() if ct else "",
            "updated": datetime.date.fromtimestamp(ut).isoformat() if ut else "",
            "score": total,
            "grade": g,
            "why": why,
            "hits": hits,
            "excerpts": excerpts(full_text, hits),
            "user_text": user_text,
            "msgs": len(all_parts),
        })
    del convs

rows.sort(key=lambda r: (-r["score"], r["created"]))
print(f"\n{len(rows)} qualified / {len(rows)+len(dropped)} scanned "
      f"({len(dropped)} below governance floor)")
print("\ntop qualifiers and the core terms driving them:")
for r in rows[:12]:
    print(f"  {r['score']:>4}  {r['grade']:<11} {r['title'][:38]:<38} {', '.join(r['t3'][:5])}")

# ------------------------------------------------------------------ output
ORDER = {"OPERATIONAL": 0, "CONFIGURED": 1, "DISCUSSED": 2}

with open(os.path.join(WORK, "chat-governance-index.md"), "w", encoding="utf-8") as f:
    f.write("# Chat governance index — CANDIDATE EVIDENCE, NOT VERIFIED\n\n")
    f.write("Source tier: `CORROBORATED-CHAT`. Insufficient alone to ship a bullet.\n")
    f.write("Grade reflects artifacts in **your own** messages, not the assistant's.\n\n")
    f.write("| # | Created | Score | Grade | Msgs | Title |\n|---|---|---|---|---|---|\n")
    for i, r in enumerate(sorted(rows, key=lambda r: (ORDER[r["grade"]], -r["score"])), 1):
        f.write(f"| {i} | {r['created']} | {r['score']} | {r['grade']} | {r['msgs']} | {r['title']} |\n")

with open(os.path.join(WORK, "chat-evidence.md"), "w", encoding="utf-8") as f:
    f.write("# Chat evidence detail — CANDIDATE, awaiting your adjudication\n\n")
    f.write("No claim below is confirmed. OPERATIONAL means you pasted output that\n")
    f.write("implies a running system; it still requires your confirmation that YOU\n")
    f.write("delivered it, not that you were evaluating someone else's system.\n\n")
    for r in sorted(rows, key=lambda r: (ORDER[r["grade"]], -r["score"])):
        if r["grade"] == "DISCUSSED":
            continue
        f.write(f"## {r['title']}\n")
        f.write(f"- created: {r['created']} | updated: {r['updated']} | score {r['score']} | **{r['grade']}**\n")
        f.write(f"- signal: `{r['why']}`\n")
        top = [t for w in (3, 2) for t, n in r["hits"].get(w, [])][:10]
        f.write(f"- terms: {', '.join(top)}\n")
        for t, frag in r["excerpts"]:
            f.write(f"  - **{t}** — {frag[:280]}\n")
        f.write("- [ ] I delivered this   - [ ] I explored this   - [ ] not my work\n\n")

seen_nums = set()
with open(os.path.join(WORK, "chat-metrics-queue.md"), "w", encoding="utf-8") as f:
    f.write("# Numbers you typed — source for metric recovery\n\n")
    f.write("These are numbers **you** wrote, recovered verbatim with context.\n")
    f.write("None is confirmed as an accomplishment metric. Per GOAL.md step 4B,\n")
    f.write("answer for each: **Measured result, or target you set?**\n")
    f.write("A target renders as \"established criteria of X\" — never an achievement.\n\n")
    f.write("| # | Conversation | Date | Number | Context (your words) | Measured or target? |\n")
    f.write("|---|---|---|---|---|---|\n")
    n = 0
    for r in sorted(rows, key=lambda r: (ORDER[r["grade"]], -r["score"])):
        if r["grade"] == "DISCUSSED":
            continue
        for m in list(NUM_PAT.finditer(r["user_text"]))[:12]:
            a, b = max(0, m.start() - 110), min(len(r["user_text"]), m.end() + 110)
            frag = norm(r["user_text"][a:b]).replace("|", "\\|")
            key = (r["id"], m.group(0).lower())
            if key in seen_nums:
                continue
            seen_nums.add(key)
            n += 1
            f.write(f"| {n} | {r['title'][:40]} | {r['created']} | **{norm(m.group(0))}** | …{frag[:200]}… |  |\n")
    print(f"{n} user-authored numbers queued")

print("\nwrote:")
for x in ("chat-governance-index.md", "chat-evidence.md", "chat-metrics-queue.md"):
    p = os.path.join(WORK, x)
    print(f"  {p}  ({os.path.getsize(p):,} bytes)")

byg = defaultdict(int)
for r in rows:
    byg[r["grade"]] += 1
print("\ngrades:", dict(byg))

qp = os.path.join(WORK, "chat-quarantine.md")
with open(qp, "w", encoding="utf-8") as f:
    f.write("# Quarantined — circular provenance\n\n")
    f.write("These conversations scored high on governance vocabulary because\n")
    f.write("they are **resume / cover letter / interview drafting sessions**.\n")
    f.write("Their vocabulary comes from the resume, not from delivered work.\n")
    f.write("Admitting them as corroboration would recycle prior model-written\n")
    f.write("claims back in as evidence for themselves. Excluded by design.\n\n")
    f.write("| Title | Score | Core terms |\n|---|---|---|\n")
    for t, s, n in sorted(quarantined, key=lambda x: -x[1]):
        f.write(f"| {t} | {s} | {n} |\n")
print(f"quarantined (circular provenance): {len(quarantined)} -> {qp}")
