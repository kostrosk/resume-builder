---
name: resume-builder
description: Conventions for working in this repo — the provenance gate, the rules that must never be broken, and what to run before shipping a change. Load before editing tailor.py, render.py, mine_chat.py, or anything under config/.
---

# Working in this repo

A resume builder whose product is the **verification gate**, not the document.
Comparable tools (Resume Matcher, ResumeLM, OpenResume, CV-Matcher) assume the
master resume is already true. This one assumes it isn't until a human says so.
Every change has to keep that true.

## The gate

`tailor.load()` returns only `confirmed: true` experiences. The gate is at
**load**, not at filter:

```python
exps = [e for e in raw if e.get("confirmed") is True]
```

Unconfirmed content is never in memory, so no downstream bug can leak it. If
you find yourself adding a filter later in the pipeline, you have moved the
gate to a place where forgetting it becomes a regression. Don't.

## Rules that are not negotiable

These are the product. Breaking one silently is worse than crashing.

- **Never invent, estimate, or infer a metric.** No number means no number.
  Asking "roughly 500 assets?" plants a figure the user will later have to
  defend in an interview.
- **A target never becomes an achievement.** `kind: target` renders as
  "established criteria of X". It is not a win.
- **Never change a fact to match a keyword.** Tailoring reorders and compresses
  which facts lead. It does not edit them.
- **Never blend two variants into wording neither source contained.**
- **The build step never reads `source/draft/`.** Enforced in `tailor.main()`.

## The verb ladder

`check_rewrite()` rejects any AI rewrite that escalates scope. The ladder is
written as `(base, past)` pairs and every surface form is generated from them,
because **a gerund makes the same claim as a past tense** — "Leading the
council" and "Led the council" are the same assertion and must sit on the same
rung. A ladder that only knows past tense has a hole in it.

Never stem an arbitrary word into a verb. `stem("governance") + "ed"` is
`"governed"`, which invents a leadership claim from a noun and blocks honest
rewrites. Match known forms exactly.

## Grading evidence from chat history

`mine_chat.py` grades on **what the user pasted, never on what the model said**.
Asking "how do I configure X" proves curiosity; pasting an error from a live X
proves X existed. When adding an export reader, the `role` split matters — text
attributed to the user becomes evidence.

Two refusals are deliberate:
- OPERATIONAL means something ran, not that the user shipped it. Everything
  still arrives `confirmed: false`.
- Resume-writing conversations are excluded. They score high on professional
  vocabulary because the user's resume is full of it, and feeding them back in
  is the resume agreeing with itself.

## Config-driven, always

Vocabulary lives in `config/mining.yaml`. Style, sections, jobs, and output
format live in `config/resume-config.yaml`. Synonyms live in
`config/synonyms.yaml`. If you are about to hardcode a term, a colour, a
section, or a threshold in Python, it belongs in a config file — the shipped
defaults are for one profession and one page design, and every user replaces
them.

## Output format

`.docx` is the default and PDF is opt-in via `output.formats`. As of 2026 the
major parsers still read Word more reliably: Workday extracts sections
measurably worse from PDF, Lever is safer on `.docx`, and only Greenhouse is at
parity. Single-column layout matters more than the container. Do not flip the
default without new evidence.

Never emit tables, text boxes, columns, headers, footers, or images. Each one
breaks applicant tracking systems.

## Privacy

The tooling is the public artifact; the career data never is.
`data/`, `work/`, `output/`, `lineage/`, `source/`, `export/`,
`config/resume-config.yaml`, and `config/profile.yaml` are gitignored.

Before committing anything new, check it does not carry an employer name, a
real person's name, a home directory path, or a count of unverified claims.
A public repo is permanent — history, forks, and search indexes outlive a
delete.

## Before you ship a change

```bash
python test_guardrails.py            # must be all-pass; it gates --llm
python run.py jd/sample-director-dg.md
```

`test_guardrails.py` falls back to `config/resume-config.example.yaml` so it
runs on a fresh clone. Keep it that way — proof you cannot run is worth
nothing. When you fix a guardrail hole, add the case that would have caught it.
