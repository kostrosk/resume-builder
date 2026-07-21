"""
run.py — end to end for one job description.

    python run.py jd/crowdstrike.md

Rebuilds the master from your edited worksheet (checkbox states preserved),
tailors, verifies the .docx, and logs the application.
"""
import os, sys, subprocess, re

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def sh(*args):
    r = subprocess.run([PY, *args], cwd=ROOT, capture_output=True, text=True)
    if r.stdout:
        print(r.stdout.rstrip())
    if r.returncode != 0:
        print(r.stderr.rstrip(), file=sys.stderr)
        sys.exit(r.returncode)
    return r.stdout


def main():
    if len(sys.argv) < 2:
        print("usage: python run.py jd/<name>.md")
        sys.exit(1)
    jd = sys.argv[1]
    if not os.path.exists(os.path.join(ROOT, jd)) and not os.path.exists(jd):
        print(f"ERROR: no such JD: {jd}")
        sys.exit(1)
    name = os.path.splitext(os.path.basename(jd))[0]

    print("== rebuilding master from worksheet ==")
    sh(os.path.join(ROOT, "build_master.py"))
    print("\n== tailoring ==")
    out = sh(os.path.join(ROOT, "tailor.py"), jd, *sys.argv[2:])

    company = name.replace("-", " ").title()
    role = ""
    txt = open(os.path.join(ROOT, jd) if os.path.exists(os.path.join(ROOT, jd)) else jd,
               encoding="utf-8").read()
    first = next((l.strip("# ").strip() for l in txt.splitlines() if l.strip()), "")
    if first:
        role = first[:80]

    sys.path.insert(0, ROOT)
    import track
    row = track.log(name, company=company, role=role)
    print(f"\n== logged to applications.csv ==\n{row['date']}  {row['company']}  "
          f"ATS {row['ats_score']}  {row['profile']}")


if __name__ == "__main__":
    main()
