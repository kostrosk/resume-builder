"""
confirm.py — tick what is true, in one file, instead of hand-editing YAML.

    python confirm.py            write work/confirm.md from your library
    python confirm.py --apply    read your ticks back into experiences.yaml

An experience is eligible only when `confirmed: true`. That flag is the whole
product, and it is a human act — nothing in this repo sets it for you, and this
script is no exception. It only carries your ticks back.

Why this exists: confirmation used to live in a checkbox worksheet. The library
moved to data/experiences.yaml and the worksheet was left behind, so the only
way to confirm anything became hand-editing a two-thousand-line YAML file.
Predictably, nothing got confirmed. Same contract as the old worksheet, current
data model.

Rewriting is surgical — only `confirmed:` lines change, and a timestamped
backup is written first. Your wording, ordering, and comments are untouched.
"""
import os, re, sys, shutil, argparse, datetime, yaml
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
EXPS = os.path.join(ROOT, "data", "experiences.yaml")
CONF = os.path.join(ROOT, "config", "resume-config.yaml")
WORK = os.path.join(ROOT, "work")
SHEET = os.path.join(WORK, "confirm.md")

TIER_NOTE = {
    "sent-resume": "from resumes you actually sent — strongest prior, still your call",
    "draft-pack": "model-written and UNVERIFIED — read every line before ticking",
    "chat-corroborated": "mined from chat history — evidence of activity, not of delivery",
}
ROW = re.compile(r"^\s*-\s*\[([ xX])\]\s*`([^`]+)`")


def load():
    if not os.path.exists(EXPS):
        sys.exit(f"ERROR: {EXPS} not found — run: python migrate.py")
    doc = yaml.safe_load(open(EXPS, encoding="utf-8")) or {}
    return doc.get("experiences") or []


def job_labels():
    if not os.path.exists(CONF):
        return {}
    cfg = yaml.safe_load(open(CONF, encoding="utf-8")) or {}
    return {j["id"]: f"{j.get('company','')} — {j.get('role','')}".strip(" —")
            for j in cfg.get("jobs", []) if j.get("id")}


def write_sheet(exps):
    labels = job_labels()
    byjob = defaultdict(lambda: defaultdict(list))
    for e in exps:
        byjob[e.get("job") or "UNASSIGNED"][e.get("tier") or "untiered"].append(e)

    done = sum(1 for e in exps if e.get("confirmed") is True)
    os.makedirs(WORK, exist_ok=True)
    with open(SHEET, "w", encoding="utf-8") as f:
        f.write("# Confirmation worksheet\n\n")
        f.write(f"**{done} of {len(exps)} confirmed.** "
                f"{len(exps) - done} are invisible to the builder right now.\n\n")
        f.write("Tick `[x]` what is true and you would defend in an interview. "
                "Leave `[ ]` on anything you are unsure of — unconfirmed content "
                "cannot reach a document, which is the point.\n\n")
        f.write("Then run:\n\n```bash\npython confirm.py --apply\n```\n\n")
        f.write("Edit the wording in `data/experiences.yaml`, not here — this "
                "file is regenerated and only the checkboxes are read back.\n\n---\n")

        for jid in sorted(byjob, key=lambda j: -len(byjob[j])):
            label = labels.get(jid, jid)
            n = sum(len(v) for v in byjob[jid].values())
            ok = sum(1 for v in byjob[jid].values() for e in v
                     if e.get("confirmed") is True)
            f.write(f"\n## {label}  ({ok}/{n} confirmed)\n")
            for tier in sorted(byjob[jid]):
                rows = byjob[jid][tier]
                note = TIER_NOTE.get(tier, "")
                f.write(f"\n### {tier}"
                        f"{'  — ' + note if note else ''}\n\n")
                for e in sorted(rows, key=lambda x: x.get("project") or ""):
                    mark = "x" if e.get("confirmed") is True else " "
                    txt = (e.get("text") or {}).get("long", "").strip()
                    proj = e.get("project")
                    metrics = [m.get("value") for m in (e.get("metrics") or [])
                               if m.get("value")]
                    f.write(f"- [{mark}] `{e['id']}`\n")
                    if proj:
                        f.write(f"      *{proj}*\n")
                    f.write(f"      {txt}\n")
                    if metrics:
                        f.write(f"      numbers: {', '.join(map(str, metrics))} "
                                f"— set `kind: measured` or `target` in the YAML\n")
                    f.write("\n")
    return SHEET, done


def read_sheet():
    if not os.path.exists(SHEET):
        sys.exit(f"ERROR: {SHEET} not found — run `python confirm.py` first.")
    ticks = {}
    for ln in open(SHEET, encoding="utf-8"):
        m = ROW.match(ln)
        if m:
            ticks[m.group(2)] = m.group(1).lower() == "x"
    return ticks


def apply(ticks, exps):
    """Rewrite only `confirmed:` lines, keyed by the id block they sit in."""
    known = {e["id"] for e in exps}
    unknown = sorted(set(ticks) - known)
    before = {e["id"]: e.get("confirmed") is True for e in exps}

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"{EXPS}.{stamp}.bak"
    shutil.copy2(EXPS, backup)

    out, cur, changed = [], None, 0
    for ln in open(EXPS, encoding="utf-8"):
        m = re.match(r"^-\s+id:\s*(.+?)\s*$", ln)
        if m:
            cur = m.group(1).strip().strip("'\"")
        elif cur is not None and re.match(r"^\s+confirmed:\s", ln):
            want = ticks.get(cur)
            if want is not None:
                indent = ln[:len(ln) - len(ln.lstrip())]
                new = f"{indent}confirmed: {'true' if want else 'false'}\n"
                if new != ln:
                    changed += 1
                ln = new
        out.append(ln)
    open(EXPS, "w", encoding="utf-8").writelines(out)

    now = sum(1 for v in ticks.values() if v)
    was = sum(1 for v in before.values() if v)
    print(f"backup    {os.path.basename(backup)}")
    print(f"changed   {changed} flag(s)")
    print(f"confirmed {was} -> {now} of {len(exps)}")
    if unknown:
        print(f"\nWARNING: {len(unknown)} id(s) in the worksheet are not in the "
              f"library and were ignored:")
        for u in unknown[:5]:
            print(f"  {u}")
    gained = [i for i in ticks if ticks[i] and not before.get(i, False)]
    if gained:
        print(f"\n{len(gained)} newly eligible. Rebuild to see the difference:")
        print("  python run.py jd/<name>.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="read work/confirm.md back into data/experiences.yaml")
    a = ap.parse_args()
    exps = load()
    if a.apply:
        apply(read_sheet(), exps)
    else:
        path, done = write_sheet(exps)
        print(f"confirmed {done} of {len(exps)}  "
              f"({len(exps) - done} invisible to the builder)")
        print(f"\n  {path}\n\nTick what is true, then: python confirm.py --apply")


if __name__ == "__main__":
    main()
