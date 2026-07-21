"""
ingest.py — Step 1. Convert old resumes to markdown, preserving wording exactly.
No cleanup, no improvement, no rewording.
"""
import os, re, sys, glob, datetime
from docx import Document

ROOT = os.path.dirname(os.path.abspath(__file__))
# Folder holding your old resumes. Override: python ingest.py <folder>
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.expanduser("~"), "Resumes")
OUT = os.path.join(ROOT, "source", "resumes")
WORK = os.path.join(ROOT, "work")
os.makedirs(OUT, exist_ok=True)
os.makedirs(WORK, exist_ok=True)

BULLET_STYLES = ("List Paragraph", "List Bullet", "ListParagraph")


def para_kind(p):
    st = (p.style.name or "") if p.style is not None else ""
    txt = p.text.strip()
    if not txt:
        return None, ""
    if st.startswith("Heading"):
        return "h", txt
    if st in BULLET_STYLES or re.match(r"^[•●▪\-\*·]\s+", txt):
        return "b", re.sub(r"^[•●▪\-\*·]\s+", "", txt)
    # all-caps short lines are section headers in most of these files
    if len(txt) < 60 and txt.upper() == txt and re.search(r"[A-Z]{3}", txt):
        return "h", txt
    # These resumes carry accomplishments as labelled paragraphs rather than
    # Word list items. Treat them as bullets or the content is lost.
    if re.match(r"^(Achievement|Impact|Leadership|Outcome|Results?|Approach|"
                r"Initiative|Contribution|Guidance|Summary|Objective|Focus|"
                r"Method|Solution|Action|Deliverable)s?\s*:", txt, re.I):
        return "b", txt
    if len(txt) >= 70:            # long prose line = substantive content
        return "b", txt
    return "p", txt


docs = {}
for fp in sorted(glob.glob(os.path.join(SRC, "*.docx"))):
    name = os.path.basename(fp)
    if name.startswith("~$"):
        continue
    d = Document(fp)
    lines, bullets = [], []
    for p in d.paragraphs:
        k, t = para_kind(p)
        if k is None:
            continue
        if k == "h":
            lines.append(f"\n## {t}")
        elif k == "b":
            lines.append(f"- {t}")
            bullets.append(t)
        else:
            lines.append(t)
    mtime = datetime.date.fromtimestamp(os.path.getmtime(fp)).isoformat()
    body = f"<!-- source: {name} | modified: {mtime} -->\n" + "\n".join(lines) + "\n"
    stem = os.path.splitext(name)[0]
    with open(os.path.join(OUT, stem + ".md"), "w", encoding="utf-8") as f:
        f.write(body)
    docs[name] = {"mtime": mtime, "text": body, "bullets": bullets, "stem": stem}
    print(f"{name:<34} {len(bullets):>3} bullets")

# ---------------------------------------------------------------- inventory
def _detect_list():
    """Employer names come from gitignored config, never from published code."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "config", "profile.yaml")
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            if ln.strip().startswith("detect:"):
                return [x.strip() for x in ln.split(":", 1)[1].split(",") if x.strip()]
    return []


_D = _detect_list()
EMPLOYER_PAT = (re.compile(r"\b(" + "|".join(re.escape(x) for x in _D) + r")\b", re.I)
                if _D else re.compile(r"(?!x)x"))

with open(os.path.join(OUT, "INVENTORY.md"), "w", encoding="utf-8") as f:
    f.write("# Resume inventory\n\n| File | Modified | Bullets | Employers named |\n|---|---|---|---|\n")
    for n, d in sorted(docs.items(), key=lambda x: -len(x[1]["bullets"])):
        emps = sorted(set(EMPLOYER_PAT.findall(d["text"])), key=str.lower)
        f.write(f"| {n} | {d['mtime']} | {len(d['bullets'])} | {', '.join(emps) or '—'} |\n")

# ------------------------------------------------------- history + variants
def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", s.lower())).strip()


def sig(s):
    w = [x for x in norm(s).split() if len(x) > 3]
    return set(w)


all_b = []
for n, d in docs.items():
    for b in d["bullets"]:
        if len(b) > 25:
            all_b.append((n, d["mtime"], b))

# group near-identical bullets across files -> VARIANT candidates
groups, used = [], set()
for i, (fi, mi, bi) in enumerate(all_b):
    if i in used:
        continue
    g, si = [(fi, mi, bi)], sig(bi)
    for j in range(i + 1, len(all_b)):
        if j in used:
            continue
        fj, mj, bj = all_b[j]
        sj = sig(bj)
        if not si or not sj:
            continue
        jac = len(si & sj) / len(si | sj)
        if jac >= 0.55:
            g.append((fj, mj, bj))
            used.add(j)
    used.add(i)
    groups.append(g)

variants = [g for g in groups if len(g) > 1 and len({norm(x[2]) for x in g}) > 1]
uniq = [g[0] for g in groups]

with open(os.path.join(WORK, "history.md"), "w", encoding="utf-8") as f:
    f.write("# Prior-role history — merged from sent resumes\n\n")
    f.write(f"{len(all_b)} bullets across {len(docs)} files -> {len(uniq)} distinct.\n")
    f.write("Wording preserved exactly as sent.\n\n## Distinct bullets\n\n")
    for fi, mi, b in sorted(uniq, key=lambda x: -len(x[2])):
        f.write(f"- {b}\n  <!-- {fi} | {mi} -->\n")

with open(os.path.join(WORK, "variants.md"), "w", encoding="utf-8") as f:
    f.write("# VARIANT — same accomplishment, different wording or numbers\n\n")
    f.write("Pick ONE wording. Never blend. Numbers that differ are the priority.\n\n")
    for k, g in enumerate(variants, 1):
        nums = {tuple(re.findall(r"\d[\d,]*%?", x[2])) for x in g}
        f.write(f"## VARIANT {k}{'  <-- NUMBERS DIFFER' if len(nums) > 1 else ''}\n")
        for fi, mi, b in g:
            f.write(f"- [ ] ({fi}, {mi}) {b}\n")
        f.write("\n")

print(f"\n{len(all_b)} bullets -> {len(uniq)} distinct, {len(variants)} variant groups")
print("wrote source/resumes/*.md, INVENTORY.md, work/history.md, work/variants.md")
