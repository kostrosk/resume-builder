"""
run.py — one command per application.

    python run.py jd/acme.md            free, no model
    python run.py jd/acme.md --llm      AI shortens long bullets

Reads config/resume-config.yaml and data/experiences.yaml.
"""
import os, sys, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def sh(*args):
    r = subprocess.run([PY, *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.stdout:
        print(r.stdout.rstrip())
    if r.returncode != 0:
        print((r.stderr or "").rstrip(), file=sys.stderr)
        sys.exit(r.returncode)


def main():
    if len(sys.argv) < 2:
        print("usage: python run.py jd/<name>.md [--llm]")
        sys.exit(1)
    jd = sys.argv[1]
    if not (os.path.exists(jd) or os.path.exists(os.path.join(ROOT, jd))):
        print(f"ERROR: no such job description: {jd}")
        sys.exit(1)
    name = os.path.splitext(os.path.basename(jd))[0]

    for f, hint in (("config/resume-config.yaml", "the config that builds the resume"),
                    ("data/experiences.yaml", "run: python migrate.py")):
        if not os.path.exists(os.path.join(ROOT, f)):
            print(f"ERROR: missing {f} — {hint}")
            sys.exit(1)

    sh(os.path.join(ROOT, "tailor.py"), jd, *sys.argv[2:])

    sys.path.insert(0, ROOT)
    import track
    import tailor
    jdp = jd if os.path.exists(jd) else os.path.join(ROOT, jd)
    meta, _ = tailor.jd_meta(open(jdp, encoding="utf-8").read())
    row = track.log(name,
                    company=meta.get("company") or name.replace("-", " ").title(),
                    role=meta.get("role", ""))
    print(f"\nlogged: {row['date']}  {row['company']}  {row['role']}  "
          f"ATS {row['ats_score']}  {row['profile']}")


if __name__ == "__main__":
    main()
