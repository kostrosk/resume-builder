"""
migrate.py — one-time: master-resume.md  ->  data/experiences.yaml

Carries over every confirmation you already made. A bullet you ticked stays
ticked; a bullet you never confirmed arrives unconfirmed.

Run once. After this, data/experiences.yaml is the source of truth and
master-resume.md is history.
"""
import os, re, sys, yaml, unicodedata
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
MASTER = os.path.join(ROOT, "master-resume.md")
CONF = os.path.join(ROOT, "config", "resume-config.yaml")
OUT = os.path.join(ROOT, "data", "experiences.yaml")

def job_hints():
    """Derive employer -> job id from your config rather than hardcoding names.
    Each hint is (company keyword, start year, job id)."""
    if not os.path.exists(CONF):
        return []
    cfg = yaml.safe_load(open(CONF, encoding="utf-8")) or {}
    hints = []
    for j in cfg.get("jobs", []):
        key = re.sub(r"[^a-z0-9]+", " ", str(j.get("company", "")).lower()).split()
        key = key[0] if key else j["id"]
        yr = re.match(r"(\d{4})", str(j.get("start", "")))
        hints.append((key, yr.group(1) if yr else None, j["id"]))
    # most specific first: entries carrying a year beat those without
    return sorted(hints, key=lambda h: (h[1] is None,))


JOB_HINTS = job_hints()
# The newest enabled job receives content from the unverified draft section.
NEWEST_JOB = JOB_HINTS[0][2] if JOB_HINTS else None

# Vocabulary used to auto-tag each experience so a job description can find it.
TAGS = {
    "data governance": ["data governance", "governance program", "governance office"],
    "governance council": ["council", "working group", "steering", "charter"],
    "operating model": ["operating model", "framework", "roadmap", "strategy"],
    "data catalog": ["catalog", "glossary", "openmetadata", "collibra", "alation"],
    "metadata": ["metadata", "data dictionary", "documentation"],
    "data quality": ["data quality", "quality monitor", "profiling", "data debt", "dq"],
    "data classification": ["classification", "tagging", "sensitivity", "us_sensitive"],
    "access control": ["access control", "rbac", "masking", "row access", "entitlement"],
    "data lineage": ["lineage", "impact analysis", "traceability"],
    "stewardship": ["steward", "data owner", "custodian"],
    "compliance": ["gdpr", "ccpa", "sox", "cmmc", "compliance", "regulatory", "audit"],
    "pii": ["pii", "phi", "sensitive data", "personal data"],
    "snowflake": ["snowflake"],
    "power bi": ["power bi", "powerbi", "report", "dashboard"],
    "salesforce": ["salesforce", "crm", "sfdc"],
    "sql": ["sql", "query", "stored procedure"],
    "etl": ["etl", "elt", "pipeline", "ingestion", "dbt", "airflow"],
    "master data": ["master data", "mdm", "reference data", "golden record"],
    "data modeling": ["data model", "dimensional", "semantic layer", "star schema"],
    "stakeholder management": ["stakeholder", "executive", "cross-functional", "presented"],
    "change management": ["adoption", "training", "literacy", "enablement", "mentor"],
    "migration": ["migration", "migrate", "cutover", "source-to-target"],
    "ai governance": ["ai governance", "responsible ai", "model governance"],
}

NUM = re.compile(r"(?<![\w.])(\$?\d[\d,]*(?:\.\d+)?)\s*(%|percent|k\b|m\b|million|"
                 r"hours?|days?|weeks?|months?|years?|fte|rows?|records?|tables?|"
                 r"columns?|assets?|users?|sources?|domains?|stewards?|reports?|"
                 r"dashboards?|pipelines?|models?|systems?|applications?|people)?", re.I)


def slug(s, n=6):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    words = [w for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 3][:n]
    return "-".join(words) or "item"


def job_for(heading, section):
    low = heading.lower()
    if "current role" in (section or "").lower() or "unverified" in (section or "").lower():
        return NEWEST_JOB
    yrs = re.findall(r"(20\d{2})", heading)
    for emp, yr, jid in JOB_HINTS:
        if emp in low and (yr is None or yr in yrs):
            return jid
    for emp, _yr, jid in JOB_HINTS:
        if emp in low:
            return jid
    return None


def tags_for(text):
    low = text.lower()
    out = [tag for tag, words in TAGS.items() if any(w in low for w in words)]
    return out or ["general"]


def metrics_for(text):
    out = []
    for m in NUM.finditer(text):
        val, unit = m.group(1), (m.group(2) or "").strip()
        if not unit and not val.startswith("$") and "%" not in val:
            continue                       # bare number without units: skip
        a = max(0, m.start() - 60)
        out.append({
            "value": (val + ("" if not unit else " " + unit)).strip(),
            "kind": "unknown",             # measured | target | unknown
            "context": re.sub(r"\s+", " ", text[a:m.end() + 40]).strip(),
        })
    return out[:3]


def main():
    if not os.path.exists(MASTER):
        print("ERROR: master-resume.md not found — nothing to migrate")
        sys.exit(1)

    section, heading = "", ""
    rows, seen = [], set()
    for ln in open(MASTER, encoding="utf-8"):
        t = ln.rstrip("\n")
        m = re.match(r"^##\s+(?!#)(.+)", t)
        if m:
            section = m.group(1).strip()
            continue
        m = re.match(r"^###\s+(.+)", t)
        if m:
            heading = m.group(1).strip()
            continue
        m = re.match(r"^\s*-\s*\[([ xX])\]\s*(.+)", t)
        if not m:
            continue
        confirmed = m.group(1).lower() == "x"
        text = m.group(2).strip()
        key = re.sub(r"[^a-z0-9]", "", text.lower())[:80]
        if key in seen:
            continue
        seen.add(key)
        jid = job_for(heading, section)
        project = heading if section and "draft source" in section.lower() else ""
        rows.append({
            "id": "",
            "job": jid,
            "project": project,
            "confirmed": confirmed,
            "tier": "sent-resume" if "prior roles" in (section or "").lower() else "draft-pack",
            "tags": tags_for(text),
            "metrics": metrics_for(text),
            "text": {"long": text, "medium": "", "short": ""},
        })

    # stable, readable ids
    counts = defaultdict(int)
    for r in rows:
        base = f"{r['job'] or 'unassigned'}-{slug(r['text']['long'], 4)}"
        counts[base] += 1
        r["id"] = base if counts[base] == 1 else f"{base}-{counts[base]}"

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    doc = {
        "_readme": [
            "Your experience library. One entry per accomplishment.",
            "confirmed: true  -> eligible to appear on a resume.",
            "confirmed: false -> invisible to the builder, no exceptions.",
            "tags     -> how a job description finds this experience.",
            "metrics  -> set kind: measured (a result) or target (a goal you set).",
            "           A target is never printed as an achievement.",
            "text.long is your wording. medium/short are optional; leave blank",
            "and the builder shortens automatically when space is tight.",
        ],
        "experiences": rows,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, width=100)

    byjob = defaultdict(lambda: [0, 0])
    for r in rows:
        byjob[r["job"] or "UNASSIGNED"][0 if r["confirmed"] else 1] += 1
    print(f"migrated {len(rows)} experiences -> {OUT}\n")
    print(f"{'job':<20} {'confirmed':>10} {'unconfirmed':>12}")
    for j, (c, u) in sorted(byjob.items(), key=lambda x: -x[1][0] - x[1][1]):
        print(f"{j:<20} {c:>10} {u:>12}")
    nm = sum(1 for r in rows if r["metrics"])
    print(f"\n{nm} experiences carry a number — all marked kind: unknown until you say")
    print("whether each was measured or a target.")


if __name__ == "__main__":
    main()
