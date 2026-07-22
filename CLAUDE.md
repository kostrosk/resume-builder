# resume-builder

A resume builder whose product is the verification gate: nothing unconfirmed
by the human can reach a document. Read
`.claude/skills/resume-builder/SKILL.md` before editing code — it holds the
conventions. `PLAYBOOK.md` is the user-facing guide; `DESIGN.md` is the why.

## Hard rules (the product, not preferences)

- Never invent, estimate, or propose a metric. No number means no number.
- Never write an experience for the user. Tools surface *their* words
  (verbatim, past tense, explicit claim-verb list) or ask *them* to speak.
- A target never becomes an achievement. `kind: target` prints as criteria.
- The gate lives at load: `tailor.load()` returns only `confirmed: true`.
  Never re-implement it as a downstream filter.
- The build never reads `source/draft/`.
- Never emit tables, text boxes, columns, headers, or footers in output.

## Execution model

This tool is designed to run inside an agentic harness. The agent is the UI,
the scripts are the deterministic substrate, the human is the verification
oracle. `/hil-interview jd/<name>.md` runs one application end-to-end as a
conversation (see `.claude/skills/hil-interview/SKILL.md`). Prefer driving
that flow over telling the user to go run terminal commands.

## Layout

- `data/experiences.yaml` + `config/resume-config.yaml` — the user's two
  files; both hand-editable, both gitignored (example configs are published).
- Miners (`mine_chat.py`, `mine_repos.py`) produce candidates in `work/`,
  always `confirmed: false`. `interview.py` asks about JD gaps and records
  the user's own answers. `confirm.py` is the only confirmation UI.
- `jd/*.md` carry YAML front matter (company, role, req, closes) — strip it
  before term matching, use it for logging.

## Before shipping any change

```bash
python test_guardrails.py              # must pass 16/16; gates --llm
python run.py jd/sample-director-dg.md # end-to-end build must succeed
```

Privacy check before committing: no employer names, personal paths, real
names, or unverified-claim counts in anything tracked. The tooling is public;
the career data never is.
