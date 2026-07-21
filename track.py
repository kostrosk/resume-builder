"""track.py — append one row per generated application to applications.csv"""
import os, csv, re, sys, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(ROOT, "applications.csv")
COLS = ["date", "company", "role", "ats_score", "profile", "gap1", "gap2", "gap3",
        "submitted", "response"]


def log(name, company="", role="", when=None):
    gp = os.path.join(ROOT, "output", f"{name}-gaps.md")
    score = profile = ""
    gaps = []
    if os.path.exists(gp):
        t = open(gp, encoding="utf-8").read()
        m = re.search(r"ATS score: \*\*(\d+)/100\*\*", t)
        score = m.group(1) if m else ""
        m = re.search(r"profile detected: \*\*(.+?)\*\*", t)
        profile = m.group(1) if m else ""
        sec = t.split("## JD terms with no matching bullet", 1)
        if len(sec) > 1:
            gaps = re.findall(r"^- (.+?)\s+\(weight", sec[1], re.M)[:3]
    gaps += [""] * (3 - len(gaps))
    row = {
        "date": when or datetime.date.today().isoformat(),
        "company": company or name,
        "role": role,
        "ats_score": score,
        "profile": profile,
        "gap1": gaps[0], "gap2": gaps[1], "gap3": gaps[2],
        "submitted": "n", "response": "",
    }
    new = not os.path.exists(CSV)
    with open(CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerow(row)
    return row


if __name__ == "__main__":
    print(log(sys.argv[1] if len(sys.argv) > 1 else "unnamed"))
