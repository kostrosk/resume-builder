# DESIGN

Why this is built the way it is. For how to use it, see [README.md](README.md).

---

## The problem

Resume tools reword what you already wrote and assume it is true. That
assumption is where the damage happens. A sentence drafted six versions ago
becomes something you have to defend in an interview, and nobody remembers
whether that "30% improvement" was measured or hoped for.

Comparable open-source tools — Resume Matcher, ResumeLM, OpenResume,
CV-Matcher — all take a master resume as ground truth and optimise presentation
against a posting. None of them verify that the content is true, and none
document any guardrail against a model inventing detail during a rewrite.

**The verification gate is the product.** Everything else here is in service of
it.

---

## Three files, one command

```
data/experiences.yaml       everything you have ever done
config/resume-config.yaml   who you are, where you worked, how the page looks
jd/<name>.md                the posting you are applying to
        │
        └──►  python run.py jd/<name>.md  ──►  output/<name>.docx
```

Both YAML files are hand-editable and both are pre-populated for you —
`ingest.py` + `migrate.py` from resumes you have already sent, `mine_chat.py`
from AI chat history. **Parsing is a head start, not a source of truth.** You
review and confirm; nothing you have not confirmed can reach a document.

The backend is deliberately a set of plain scripts over flat files. A UI can be
layered on later precisely because state lives in editable YAML rather than in
an application.

---

## The gate

An experience is eligible only when `confirmed: true`. The gate lives at
**load**, not at filter:

```python
exps = [e for e in raw if e.get("confirmed") is True]
```

Unconfirmed content is never in memory, so no downstream bug can leak it into
output. Absence of a filter cannot become a regression. This is the single most
important line in the codebase.

---

## Data model

An experience record:

| Field | Meaning |
|---|---|
| `id` | stable slug, referenced by lineage |
| `job` | foreign key to `jobs[].id` in the config |
| `confirmed` | `true` = eligible. **The gate.** |
| `tier` | `sent-resume` / `draft-pack` / `chat-corroborated` |
| `tags` | curated retrieval keys, weighted above incidental body text |
| `metrics[]` | `value`, `kind` (`measured` / `target` / `unknown`), `context` |
| `text` | `long` / `medium` / `short` — all your wording |

`kind: target` matters. A number you aimed at renders as "established criteria
of X", never as a result you hit.

A job record carries `id`, `company`, `ticker`, `role`, `location`, `start`,
`end`, `enabled`, `max_bullets`, `priority`. Toggling `enabled` or reordering
`sections` permutes the document with no regeneration and no code change. One
library, unlimited resumes.

---

## Matching

Deterministic, not embeddings. Three tiers of evidence that an experience fits
a posting:

| Source | Weight |
|---|---|
| body text | 1 — incidental language |
| `tags` | `tag_weight` — vocabulary you curated |
| `match` | `match_weight` — keywords you added by hand |

Plus stemming, a hand-editable synonym map (`config/synonyms.yaml`), and
positional weighting — terms near the top of a posting and inside bullets count
for more.

Embeddings would match better on paraphrase. They are not used because every
shipped line has to be traceable to the words that earned it; `lineage/` would
become "the vector said so". Determinism is what makes the audit trail real.

The posting is also classified by seniority, and the profile changes which
facts lead and which compress — never what the facts are. A posting that reads
below the target level is flagged rather than written down to.

---

## Rewriting, and why the model is not trusted

Long bullets must shorten to fit one page. With `--llm`, a model proposes the
shortening. Ordinary code then decides whether to accept it. A rewrite is
discarded if it:

- introduces a number absent from the source
- introduces a tool, company, or system absent from the source
- **escalates the claim** — `helped` may not become `led`
- comes back longer than the original

Rejected rewrites fall back to `trim()`, which cuts at clause boundaries and
invents nothing. Every rewrite is written beside its original for review before
sending.

The escalation ladder is stored as `(base, past)` pairs and all surface forms
are generated, because a gerund makes the same claim as a past tense —
"Leading the council" asserts exactly what "Led the council" asserts. A ladder
that knows only past tense has a hole in it, and that hole was real until it
was closed.

`test_guardrails.py` proves the checks block what they claim to. It falls back
to the example config so it runs on a fresh clone: proof you cannot run is
worth nothing.

---

## Mining chat history

If you have spent years asking an AI for help at work, you kept a work diary
without meaning to — timestamped, in your own words, recording things you
forgot within a month of shipping them.

Evidence is graded on **what you pasted, never on what the model said**:

| Grade | Meaning |
|---|---|
| OPERATIONAL | output only a running system produces — traces, error codes, result rows |
| CONFIGURED | code or config you pasted |
| DISCUSSED | topic appears, no artifact |

Asking "how do I configure X" proves curiosity. Pasting an error from a live X
proves X existed.

Two deliberate refusals. OPERATIONAL means something ran, not that you shipped
it rather than evaluated it — so everything still arrives `confirmed: false`.
And resume-writing conversations are excluded automatically: they score high on
professional vocabulary because your resume is full of it, and feeding them
back in is just the resume agreeing with itself.

Readers exist for ChatGPT, Claude, Google Takeout, generic JSON, and folders of
markdown or text. Vocabulary is entirely config-driven (`config/mining.yaml`) —
the shipped defaults describe one profession and are meant to be replaced.

---

## Output format

`.docx` by default, PDF opt-in via `output.formats`.

As of 2026 the major parsers still read Word more reliably than PDF. Workday
extracts sections measurably worse from PDF; Lever is safer on `.docx`; only
Greenhouse is at genuine parity. The container matters far less than the
layout, which is why the renderer emits no tables, text boxes, columns,
headers, footers, or images — each one breaks applicant tracking systems.

PDF is worth enabling when a human is the reader or a portal demands it. No
converter is bundled; Word or LibreOffice does the work, and if neither is
present that is reported rather than silently producing nothing.

Every generated document is re-opened and re-parsed before you see it. A resume
that will not parse is a resume nobody reads.

---

## Getting read: the funnel, and why "overwhelm the ATS" is a trap

The goal is not a high ATS score. It is a hiring manager reading the resume,
and that sits at the end of a funnel:

```
ATS parse → recruiter keyword search → recruiter 6-second skim → shortlist → hiring manager
```

Most resumes die at the recruiter search and skim, not at the parse. **No
compliant method guarantees a human reads a resume** — anyone promising a
guarantee is selling fraud, a referral they do not control, or luck. What the
tool maximises is the probability at every stage:

1. **Referral** beats everything below combined and is fully compliant. The
   tool cannot manufacture one, but the strategy names it first honestly.
2. **Parse perfection** — single column, no tables, re-parsed after every
   build, `.docx` by default. Zero points lost here.
3. **Saturation of *true, confirmed* coverage** — recruiters run boolean
   searches ("data governance" AND "Collibra" AND "council"). Every confirmed
   claim using the posting's own nouns is another query the candidate matches.
   This is what "overwhelm" legitimately means: distributed, contextual,
   truthful coverage — which modern semantic scorers reward and repetition
   they discount. The ceiling here is confirmation, not the renderer.
4. **Exact-phrase alignment** — where confirmed experience genuinely *is* what
   the posting describes in other words, the bullet uses the posting's
   phrasing. Translation, not invention; `check_rewrite()` polices the line.
   The `hil-interview` skill does this as a HIL step: it proposes the minimal
   term-swap, validates it against the truthfulness guards (no new number, no
   new tool/company, no scope escalation — the length guard is dropped because
   the JD's phrase is often longer), and applies only what the user approves.
   Pure keyword lift with no prose risk goes into an experience's `match:`
   field instead, which stays honest across every future posting.
5. **The human skim** — target title mirrored in the headline where truthful,
   strongest program-ownership bullets in the top third, a real education
   section present.

Keyword stuffing, hidden text, and instructions aimed at an AI screener are
not something this tool can produce: output is plain single-column text with no
hidden channel, and the tool never composes a bullet. The only way such content
enters is through a source document — and the confirmation step is a human
reading their own bullets verbatim before any of them can ship. That review,
not a phrase blocklist, is the defense; a blocklist of known payloads is
whack-a-mole that any rewording defeats.

---

## Privacy

The tooling is the public artifact. The career data never is.

`data/`, `work/`, `output/`, `lineage/`, `source/`, `export/`, your real
`config/resume-config.yaml`, and your application log are all gitignored. Fork
this publicly and your phone number, employment history, and chat exports stay
on your machine.

---

## Not built yet

Cover letters, reading postings from a URL, application autofill, a web UI,
and structured Education / Certifications sections — those are currently a
free-text block rather than parsed fields.
