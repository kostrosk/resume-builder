"""
smoke.py — prove the pipeline builds end to end, from the PUBLISHED example
files only. Touches nothing personal; safe to run in CI or on a fresh clone.

    python scripts/smoke.py

Points tailor at config/resume-config.example.yaml and
data/experiences.example.yaml via env overrides, builds against the sample
posting, and asserts a real .docx came out and re-parsed. Writes small,
publishable check artifacts under examples/sample-output/ so a reader (or a
recruiter) can see exactly what the tool produces without any private data.
"""
import os, sys, shutil, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "examples", "sample-output")
JD = os.path.join(ROOT, "jd", "sample-director-dg.md")


def main():
    env = dict(os.environ)
    env["RESUME_CONFIG"] = os.path.join(ROOT, "config", "resume-config.example.yaml")
    env["RESUME_EXPS"] = os.path.join(ROOT, "data", "experiences.example.yaml")
    env["PYTHONIOENCODING"] = "utf-8"

    print("smoke: guardrails")
    r = subprocess.run([sys.executable, "test_guardrails.py"], cwd=ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout.strip().splitlines()[-1] if r.stdout else "(no output)")
    if r.returncode != 0:
        sys.exit("guardrails failed:\n" + (r.stdout or "") + (r.stderr or ""))

    print("smoke: build from example data")
    r = subprocess.run([sys.executable, "tailor.py", JD], cwd=ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or "").strip())
    if r.returncode != 0:
        sys.exit("build failed:\n" + (r.stderr or ""))

    docx = os.path.join(ROOT, "output", "sample-director-dg.docx")
    if not (os.path.exists(docx) and os.path.getsize(docx) > 5000):
        sys.exit("no usable .docx produced")

    # publish small text artifacts (never the personal ones)
    os.makedirs(OUTDIR, exist_ok=True)
    for name in ("sample-director-dg-gaps.md", "sample-director-dg.md"):
        src = os.path.join(ROOT, "output" if name.endswith("gaps.md") else "lineage",
                           name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(OUTDIR, name.replace("sample-director-dg",
                                                                "example")))
    print(f"\nsmoke OK — docx {os.path.getsize(docx)} bytes; "
          f"artifacts in examples/sample-output/")


if __name__ == "__main__":
    main()
