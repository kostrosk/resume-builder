"""
build_master.py — assemble master-resume.md as an EDITABLE WORKSHEET.

Every bullet carries a checkbox. tailor.py ships ONLY `- [x]` lines.
Confirmation is therefore a manual act, and unconfirmed content is
mechanically incapable of reaching a .docx.

  [x] appeared in a resume you actually sent      -> default confirmed
  [ ] drawn from the UNVERIFIED draft source pack -> you must confirm
  [ ] variant conflict, you must pick one wording

Re-running preserves your edits: existing checkbox states are read back in
before the file is rewritten.
"""
import os, re, glob, json

ROOT = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(ROOT, "source", "resumes")
# Any markdown file dropped in source/draft/ is treated as the unverified pack.
_packs = sorted(glob.glob(os.path.join(ROOT, "source", "draft", "*.md")))
PACK = _packs[0] if _packs else None
WORK = os.path.join(ROOT, "work")
MASTER = os.path.join(ROOT, "master-resume.md")

ROLE_PAT = re.compile(
    r"^(?P<title>[^|]{3,70})\|(?P<emp>[^|]{2,40})\|\s*(?P<dates>[A-Za-z]{3,9}\.?\s*\d{4}\s*[–\-—to]+\s*(?:[A-Za-z]{3,9}\.?\s*\d{4}|Present|Current))",
    re.I)


ROLE_DATES = {}


def load_profile():
    """Identity and employer names live in config/profile.yaml, which is
    gitignored. Nothing personal belongs in tooling that gets published."""
    p = os.path.join(ROOT, "config", "profile.yaml")
    name, emps = "", []
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            ln = ln.strip()
            if not ln or ln.startswith("#") or ":" not in ln:
                continue
            k, v = (x.strip() for x in ln.split(":", 1))
            if k == "name":
                name = v
            elif k == "employer":
                parts = [x.strip() for x in v.split("|")]
                canon = parts[0]
                for alias in (parts[1:] or [canon]):
                    emps.append((rf"\b{re.escape(alias.lower())}\b", canon))
    return name, emps


PROFILE_NAME, EMP_CANON = load_profile()


def canon_role(emp, title, dates):
    """Each resume formats the role header differently — 'CQG', 'CQG, Inc.',
    or a city with the employer buried in the title. Without canonicalising,
    one job fragments into several and the resume prints duplicate roles."""
    emp, title = emp.strip(), re.sub(r"^#+\s*", "", title).strip()
    blob = f"{emp} {title}".lower()
    for pat, name in EMP_CANON:
        if re.search(pat, blob):
            emp = name
            break
    else:
        if re.match(r"^[A-Z][a-z]+,\s*[A-Z]{2}$", emp):      # "Denver, CO"
            at = re.search(r"@\s*(.+)$", title)
            emp = at.group(1).strip() if at else emp
    title = re.sub(r"\s*@.*$", "", title)
    title = re.sub(r"\s*\((CONTINUED|CONT\.?|PROMOTION)\)\s*", " ", title, flags=re.I)
    title = re.sub(r"\s+", " ", title).strip().title()
    yr = re.search(r"(\d{4})", dates)
    key = (emp, title, yr.group(1) if yr else "")
    d = dates.strip()
    if len(d) > len(ROLE_DATES.get(key, "")):
        ROLE_DATES[key] = d
    return key


# These resumes prefix accomplishments with an ad-hoc label — Achievement:,
# Creation:, Significance:, Efficiency: — an open set, so match the shape
# rather than enumerating. One to three capitalised words then a colon.
LABEL = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Za-z]+){0,2}\s*:\s+(?=[A-Za-z])")


def clean_bullet(t):
    """Strip source formatting labels. These are document scaffolding, not
    wording — 'Achievement: Directed X' is the same claim as 'Directed X'.
    Returns None for headings and fragments that are not accomplishments."""
    t = LABEL.sub("", t).strip()
    t = re.sub(r"\s+", " ", t)
    if len(t) < 40:
        return None
    if t.endswith(":"):                     # section heading, not a bullet
        return None
    if not re.search(r"\b[a-z]{3,}\b.*\b[a-z]{3,}\b", t):
        return None
    return t[0].upper() + t[1:]


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", s.lower())).strip()


def _stem(w):
    for suf in ("ization", "ations", "ation", "ances", "ance", "ments", "ment",
                "ings", "ing", "ies", "ied", "ers", "er", "ed", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def sig(s):
    # stem before comparing, or 'establish/established' read as distinct claims
    # and the same accomplishment ships twice on a one-page resume
    return {_stem(w) for w in norm(s).split() if len(w) > 3}


# ------------------------------------------------- preserve prior decisions
prior = {}
if os.path.exists(MASTER):
    for ln in open(MASTER, encoding="utf-8"):
        m = re.match(r"\s*-\s*\[([ xX])\]\s*(.+)", ln)
        if m:
            prior[norm(m.group(2))[:90]] = m.group(1).lower() == "x"
    print(f"preserving {len(prior)} prior checkbox decisions")

# ---------------------------------------------------------- prior roles
roles = {}
for fp in sorted(glob.glob(os.path.join(RES, "*.md"))):
    if fp.endswith("INVENTORY.md"):
        continue
    src = os.path.basename(fp)
    cur = None
    for ln in open(fp, encoding="utf-8"):
        t = ln.rstrip("\n")
        raw = re.sub(r"^-\s+", "", t).strip()
        if not raw or raw.startswith("<!--"):
            continue
        m = ROLE_PAT.match(raw)
        if m:
            cur = canon_role(m.group("emp"), m.group("title"), m.group("dates"))
            roles.setdefault(cur, [])
            continue
        if t.startswith("## ") or len(raw) < 30:
            continue
        if cur:
            cb = clean_bullet(raw)
            if cb:
                roles[cur].append((cb, src))

# dedupe within role, keep longest phrasing, flag variants
clean = {}
for r, items in roles.items():
    kept = []
    for txt, src in sorted(items, key=lambda x: -len(x[0])):
        s = sig(txt)
        hit = None
        for k in kept:
            ks = sig(k["text"])
            if not s or not ks:
                continue
            jac = len(s & ks) / len(s | ks)
            # containment: a truncated restatement is the same claim, but its
            # Jaccard against the fuller version is low. Catch it explicitly or
            # both ship and the resume repeats itself.
            cont = len(s & ks) / min(len(s), len(ks))
            if jac >= 0.55 or cont >= 0.80:
                hit = k
                break
        if hit:
            if norm(txt) != norm(hit["text"]):
                hit["variants"].append((txt, src))
        else:
            kept.append({"text": txt, "src": src, "variants": []})
    clean[r] = kept

# ---------------------------------------------------------- draft claims
CLAIM_SECTIONS = ("Defensible Scope Statements", "Core Deliverables",
                  "Deliverables", "Likely Deliverables", "Candidate Responsibilities",
                  "Technical Implementation", "Governance Artifacts",
                  "Technical Control Areas", "Technical Methods")
projects, cur_proj, cur_sec = {}, None, None
for ln in (open(PACK, encoding="utf-8") if PACK else []):
    t = ln.rstrip("\n")
    m = re.match(r"^#\s+(\d+)\.\s*(.+)", t) or re.match(r"^##\s+(\d+)\.\s*(.+)", t)
    if m:
        cur_proj = m.group(2).strip()
        projects.setdefault(cur_proj, [])
        cur_sec = None
        continue
    m = re.match(r"^#{2,3}\s+(.+)", t)
    if m:
        cur_sec = m.group(1).strip()
        continue
    if cur_proj and cur_sec and any(cur_sec.startswith(c) for c in CLAIM_SECTIONS):
        b = re.match(r"^\s*[-*]\s+(.+)", t)
        if b:
            txt = re.sub(r"\*\*", "", b.group(1)).strip()
            if len(txt) > 30:
                projects[cur_proj].append((txt, cur_sec))

# --------------------------------------------------------- chat corroboration
chat = []
idx = os.path.join(WORK, "chat-governance-index.md")
if os.path.exists(idx):
    for ln in open(idx, encoding="utf-8"):
        m = re.match(r"\|\s*\d+\s*\|\s*([\d-]+)\s*\|\s*(\d+)\s*\|\s*(\w+)\s*\|\s*\d+\s*\|\s*(.+?)\s*\|", ln)
        if m:
            chat.append({"date": m.group(1), "score": int(m.group(2)),
                         "grade": m.group(3), "title": m.group(4)})


def corroborate(text, k=2):
    s = sig(text)
    out = []
    for c in chat:
        if c["grade"] == "DISCUSSED":
            continue
        ov = s & sig(c["title"])
        if len(ov) >= 2:
            out.append((len(ov), c))
    out.sort(key=lambda x: (-x[0], -x[1]["score"]))
    return [c for _, c in out[:k]]


def box(text, default):
    return "x" if prior.get(norm(text)[:90], default) else " "


# ------------------------------------------------------------------- write
def sort_key(r):
    d = ROLE_DATES.get(r, "")
    m = re.search(r"(\d{4})\s*[–\-—to]+\s*(?:(\d{4})|Present|Current)", d, re.I)
    end = 9999 if (m and not m.group(2)) else (int(m.group(2)) if m else 0)
    return (-end, -int(r[2] or 0))

n_conf = n_open = 0
with open(MASTER, "w", encoding="utf-8") as f:
    f.write("# Master Resume — WORKSHEET\n\n")
    f.write("`[x]` = confirmed true, eligible to ship.  `[ ]` = not confirmed, "
            "will NOT appear in any generated resume.\n\n")
    f.write("Edit freely. Rewrite wording in your own voice. Delete what is wrong. "
            "Re-run `python build_master.py` and your checkbox states are preserved.\n\n")
    f.write("**Metrics:** a number only ships if it is a measured result. If it was a "
            "target you set, rewrite the bullet as \"established criteria of X\".\n\n---\n\n")

    f.write("## CURRENT ROLE — UNVERIFIED DRAFT SOURCE (confirm each line)\n\n")
    f.write("> Source: `source/draft/ansys-source-pack.md`, model-written. "
            "Nothing here is evidence. Chat corroboration shows you *worked on* the "
            "topic near that date — it does not prove you delivered it.\n\n")
    for p, claims in projects.items():
        if not claims:
            continue
        f.write(f"### {p}\n\n")
        seen = set()
        for txt, sec in claims:
            txt = clean_bullet(txt) or txt
            key = norm(txt)[:90]
            if key in seen:
                continue
            seen.add(key)
            b = box(txt, False)
            n_conf += (b == "x")
            n_open += (b == " ")
            f.write(f"- [{b}] {txt}\n")
            cs = corroborate(txt)
            if cs:
                tags = "; ".join(f"{c['title']} ({c['date']}, {c['grade']})" for c in cs)
                f.write(f"      <!-- chat: {tags} -->\n")
        f.write("\n")

    f.write("---\n\n## PRIOR ROLES — from resumes you actually sent\n\n")
    for r in sorted(clean, key=sort_key):
        emp, title, _yr = r
        items = clean[r]
        if not items:
            continue
        f.write(f"### {emp} — {title} | {ROLE_DATES.get(r,'')}\n\n")
        for it in items:
            has_var = bool(it["variants"])
            b = box(it["text"], not has_var)
            n_conf += (b == "x")
            n_open += (b == " ")
            f.write(f"- [{b}] {it['text']}\n")
            f.write(f"      <!-- {it['src']} -->\n")
            for vt, vs in it["variants"]:
                f.write(f"      <!-- VARIANT ({vs}): {vt} -->\n")
        f.write("\n")

print(f"roles: {len(clean)} | draft projects: {sum(1 for v in projects.values() if v)}")
print(f"bullets: {n_conf} confirmed / {n_open} awaiting confirmation")
print(f"wrote {MASTER}")
