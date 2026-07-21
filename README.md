# resume-builder

Turn old resumes, years of AI chat history, and your code projects into one
resume library, then generate a tailored, one-page resume for any job posting.

**New here? Read [PLAYBOOK.md](PLAYBOOK.md)** — the plain-language guide to
every file and every workflow. This README is the reference;
[DESIGN.md](DESIGN.md) is the reasoning.

---

## What

Three files you own, one command.

```
data/experiences.yaml       everything you have ever done
config/resume-config.yaml   where you worked + how the page looks
jd/acme.md                  the posting you are applying to
        │
        └──►  python run.py jd/acme.md  ──►  output/acme.docx
```

You never edit code.

---

## Why

**Most resume tools reword what you already wrote. They assume it is true.**

It usually isn't. A sentence you drafted six versions ago becomes something you
have to defend in an interview, and nobody remembers whether that "30% improvement"
was measured or hoped for.

This tool inverts that. Every accomplishment starts **unconfirmed**. You mark it
true once. Anything unconfirmed is never loaded by the builder, so it cannot reach
a document by accident.

Three rules it will not break:

- It never invents a number. No metric means no metric.
- A target you set never becomes an achievement you hit.
- It tells you when you are underqualified instead of padding to hide it.

---

## How

### 1. Install

```bash
pip install python-docx pyyaml
```

### 2. Required inputs

| Input | Needed? | Where |
|---|---|---|
| Old resumes (`.docx`) | to start fast | any folder — `python ingest.py <folder>` |
| AI chat export | optional, high value | `./export/` — see below |
| Job posting | per application | `jd/<name>.md` — paste the text, add facts up top (see below) |
| Your details | once | `config/resume-config.yaml` |

You need at least one of: old resumes, an AI export, or the patience to write
experiences by hand.

### 3. Configure

```bash
cp config/resume-config.example.yaml config/resume-config.yaml
```

Open it. Everything you can change is in that one file:

**Who you are** — name, headline, location, phone, email, and any number of links.

```yaml
links:
  - {label: LinkedIn,  url: linkedin.com/in/you,  show: true}
  - {label: GitHub,    url: github.com/you,       show: true}
  - {label: Substack,  url: "",                   show: false}
```

`show: false` benches a link without deleting it.

**Where you worked** — add an entry and its experiences become eligible.

```yaml
- id: current
  company: Acme Corporation
  ticker: ACME          # prints "Acme Corporation (ACME)", "" hides it
  role: Director, Data Governance
  start: 2024-07
  end: present
  enabled: true         # false drops the job entirely
  max_bullets: 10       # most lines this job can take
  priority: 10          # who wins when space runs out
```

**What appears** — reorder the `sections` list and the page reorders. Turn a
section off with `enabled: false`.

**How it looks** — fonts, sizes, colours, margins, spacing, bullet character,
date format. All declarative. `**bold**` and `*italic*` inside any bullet become
real Word formatting.

### 4. Build your library

```bash
python ingest.py ~/Resumes     # read old resumes
python migrate.py              # turn them into experiences
```

You now have `data/experiences.yaml`, with duplicates merged and conflicting
versions flagged. Everything arrives unconfirmed.

### 5. Confirm what is true

```bash
python confirm.py            # writes work/confirm.md — tick what is true
python confirm.py --apply    # carries your ticks back into the library
```

**Nothing you have not confirmed can reach a document.** That is the gate, and
it is the reason this tool exists — so it is also the step people skip and then
wonder why their resume is thin. Unconfirmed experiences are not hidden or
deprioritised, they are never loaded at all.

Tick what you would defend in an interview. Leave anything you are unsure of
alone. `confirm.py` never sets the flag for you; it only carries your ticks,
writes a timestamped backup first, and touches nothing but `confirmed:` lines.

`python propose.py jd/<name>.md` will tell you which unconfirmed experiences
would match a specific posting — the fastest way to know which ticks are worth
your time.

An experience looks like this:

```yaml
- id: acme-catalog
  job: acme                      # matches a job id in your config
  confirmed: false               # ← flip to true once you verify it
  tags: [data catalog, metadata, stewardship]
  metrics:
    - value: "40 tables"
      kind: measured             # measured | target | unknown
  text:
    long: "Established a data catalog and **business glossary**, documenting
           40 critical tables."
```

`tags` is how a posting finds it. `kind: target` means you aimed at that number,
not that you hit it — those print as "established criteria of X", never as a win.

### 6. Apply

Start the posting file with its facts, then paste the text below them:

```yaml
---
company: Acme Corporation
role: Director, Data Governance
req: R-12345            # requisition / posting id
location: Remote (US)
salary: $170,000-$260,000
closes: 2026-09-06
---
```

All optional — but company and role flow into your application log and the
gaps report, and the requisition id is the thing recruiters ask for.

```bash
python propose.py jd/acme.md    # what should go on this resume, and why
python run.py jd/acme.md        # build it
python interview.py jd/acme.md  # be asked about the gaps (see below)
```

`propose.py` answers three questions and changes nothing:

1. Which experiences already match, and which words earned the match
2. Which would match **but are not confirmed** — value you are sitting on
3. Which posting terms you cover nowhere, with the nearest experience you have
   and the exact line to add **if it genuinely applies**

You get back:

| File | What it is |
|---|---|
| `output/acme.docx` | The resume you send |
| `output/acme-gaps.md` | What the job wanted that you cannot back up |
| `lineage/acme.md` | Where every line came from |

### 7. Tune it

When the automatic match gets something wrong, four knobs on any experience:

```yaml
match:   [operating model, decision rights]   # your keywords, weighted highest
boost:   1.5        # push this one up
pin:     true       # always include it
exclude: true       # never include it
```

---

## Mining your AI chat history

```bash
python mine_chat.py                        # reads ./export
python mine_chat.py --source ~/Downloads/chats
python mine_chat.py --jd jd/acme.md        # aim it at a posting
python mine_chat.py --pull-claude          # grab Claude Code history off disk
```

Reads exports from **ChatGPT, Claude, Claude Code, Google Takeout, generic
JSON, or any folder of markdown and text files.** Formats are detected per
file, and a folder holding several kinds is mined in one pass. Getting the
exports: ChatGPT is Settings → Data controls → Export; claude.ai is Settings →
Privacy → Export data (arrives by email — unzip into `./export/`). Claude Code
needs no export at all: `--pull-claude` copies its transcripts straight off
your disk, skipping this tool's own sessions so the resume cannot cite itself.

For Gemini, choose **JSON** when you request the Takeout export. Takeout defaults
to `MyActivity.html`, which is not parsed — point `--source` at HTML and the tool
says so rather than reporting an empty result. Takeout records one activity per
prompt with no conversation boundaries, so a day of prompts is grouped into one
entry.

### Why this matters

If you have spent two years asking an AI for help at work, you have been keeping a
work diary without meaning to. It is timestamped, it is in your own words, and it
records the things you *actually did* — including the ones you forgot within a
month of shipping them.

That is the hardest gap in any resume. You remember the big project. You do not
remember the migration you unblocked in March, the classification rules you wrote,
or that you once processed 500,000 columns. Your chat history does.

### How it grades evidence

Not all chat history is equal, and the difference is detectable:

| Grade | What it means | Strength |
|---|---|---|
| **OPERATIONAL** | You pasted output only a running system produces — stack traces, error codes, result rows, logs | Strongest |
| **CONFIGURED** | You pasted code or config | You built something |
| **DISCUSSED** | The topic appears, no artifact | You explored it |

It grades on **what you pasted, not what you asked**, and recovers numbers *you
typed* rather than numbers the AI suggested. Asking "how do I configure X" proves
curiosity. Pasting an error from a live X proves X existed.

### What becomes a candidate

Sentences **you typed that assert completed work**, quoted verbatim — past
tense only. *"Created a masking policy"* is a claim; *"Create a masking
policy"* is you telling a model what to do, and *"we need to mask PII"* is
intent, not delivery. Neither becomes a candidate.

The verbs that count are an explicit list (`claim_verbs` in
`config/mining.yaml`) plus the scope ladder the rewrite guardrail already
knows. Add your field's verbs to widen what gets *surfaced* — nothing you add
ever widens what gets *published*, because every candidate arrives
`confirmed: false` with the evidence attached: the conversation, the date, the
grade, and a `shipped` note telling you what still needs verifying. The tool
finds claims you already made. It never writes one for you.

### Aiming at a posting

`--jd jd/<name>.md` adds the posting's own recurring phrases to the mining
vocabulary. Work you described in the posting's language — "governance
council", "data ownership", "operating model" — gets surfaced even when your
base vocabulary would have missed it. Same rules: your sentences, past tense,
everything unconfirmed until you say otherwise.

### Two things it refuses to do

**It will not treat a conversation as proof of delivery.** OPERATIONAL means
something ran — not that you were the one who shipped it rather than the one
evaluating it. You still confirm every entry.

**It will not read your resume-writing sessions.** Those score high on your
professional vocabulary because your resume is full of it. Feeding them back in
would just be your resume agreeing with itself. They are excluded automatically.

### Set your vocabulary first

```bash
# edit this before your first run
config/mining.yaml
```

The shipped vocabulary is for a data governance career. **If that is not your
field, replace the terms or the miner will find nothing.** Three tiers: `core`
(words that define your profession), `supporting`, and `ambient` (common tooling,
capped so it can never qualify a conversation alone).

Output lands in `work/mined-candidates.yaml`, pre-formatted for your experience
library, every entry `confirmed: false`. You write the real wording and move
across the ones that are true.

---

## Being asked about your gaps

```bash
python interview.py jd/acme.md
```

The gaps report tells you what a posting wants that nothing confirmed covers.
This asks you about each one, in order of how much the posting cares:

1. the term, and the posting's own sentence using it
2. the nearest thing already in your library — often the honest answer is
   "confirm that one", not "write something new"
3. then it listens. **Your answer, in your words, becomes the experience —
   verbatim.** It never suggests wording, never proposes a number, and a
   skipped question stays a gap, which is the truthful outcome.

Each answer ends with one direct question — *would you defend that sentence in
an interview?* — and only a yes marks it confirmed. Entries land in
`data/experiences.yaml` under `tier: interviewed`, editable like everything
else, with a timestamped backup written first.

---

## Mining your code projects

```bash
python mine_repos.py                       # local git repos (Antigravity workspace included)
python mine_repos.py --root ~/projects     # any folder of repos
python mine_repos.py --agent-notes         # + your IDE agent's session notes
```

Surfaces each repo's own description, commit span, languages, and which of
your vocabulary it touches. With `--agent-notes`, claim sentences from IDE
agent walkthroughs too. **These are one tier weaker than chat mining** — a
README or an agent's summary is usually model-written, so every candidate says
so and everything lands unconfirmed: verify it happened, check no employer
code is inside, rewrite in your words.

---

## Using it while employed

This is the version that compounds.

The hard part of a resume is not writing it. It is remembering. Finish something
worth mentioning on a Thursday, spend four minutes:

```yaml
- id: acme-lineage-rollout
  job: acme
  confirmed: true
  tags: [data lineage, impact analysis]
  metrics:
    - value: "12 sources"
      kind: measured
  text:
    long: "Delivered end-to-end lineage across 12 upstream sources."
```

Three years later that line is still there, with the number you measured while you
still knew it. Re-run `mine_chat.py` every few months to catch what you forgot.

**When you are job hunting**, the library is already built. A new posting costs one
command, not a weekend. Add postings to `jd/`, run each, and every resume is
tailored from the same verified set of facts.

---

## Optional: AI rewriting

Long bullets must be shortened to fit one page. `--llm` lets a model do it:

```bash
python run.py jd/acme.md --llm       # needs ANTHROPIC_API_KEY
```

**The model is not trusted.** Every rewrite is re-checked by ordinary code and
discarded if it:

- introduces a number that was not in your original
- introduces a tool, company, or system that was not in your original
- strengthens the claim — `helped` may not become `led`, `designed` may not
  become `implemented`, `helped establish` may not become `established`
- comes back longer than what it replaced

Rejected rewrites fall back to trimming at a sentence break, which invents nothing.
Every rewrite lands in `output/<name>-rewrites.md` with your original beside it.

```bash
python test_guardrails.py     # proves the checks actually block bad rewrites
```

Without `--llm`, no model runs and each application costs nothing.

---

## Privacy

`config/resume-config.yaml`, `data/experiences.yaml`, `work/`, `output/`,
`lineage/`, and `export/` are all gitignored. Fork this publicly and your phone
number, career history, and chat exports stay on your machine.

---

## Files

| File | Job |
|---|---|
| `ingest.py` | Read old `.docx` resumes into text |
| `migrate.py` | Turn them into your experience library |
| `confirm.py` | Tick what is true — the gate everything else depends on |
| `mine_chat.py` | Find forgotten work in AI chat exports |
| `mine_repos.py` | Surface project evidence from git repos and agent notes |
| `interview.py` | Ask you about a posting's gaps; record your answers |
| `propose.py` | Read a posting, say what to add and why |
| `tailor.py` | Match, select, score |
| `render.py` | Style and write the Word document |
| `run.py` | All of it, one command |
| `track.py` | Log applications to a spreadsheet |
| `test_guardrails.py` | Prove the rewrite checks work |

## Not built yet

Cover letters, reading postings from a URL, autofilling applications, a web UI,
structured Education / Certifications sections.

---

## Output format: .docx or PDF

```yaml
output:
  formats: [docx]           # [docx] | [docx, pdf] | [pdf]
  pdf_engine: auto          # auto | word | libreoffice
```

**`.docx` is the default on purpose.** As of 2026 the major parsers still read
Word more reliably than PDF: Workday extracts sections measurably worse from
PDF, Lever is safer on `.docx`, and only Greenhouse is at genuine parity. If you
are optimising for getting through the screen, send Word.

Turn PDF on when a human is the reader, or when a portal demands it. No
converter is bundled — install either:

```bash
pip install docx2pdf        # drives Microsoft Word
                            # or install LibreOffice (soffice)
```

If neither is present the build says so instead of silently skipping the file.

The container matters much less than the layout. Single column, plain headings,
no tables, no text boxes, no headers or footers — applicant tracking systems
mangle anything fancier, in either format. Every file is re-opened and re-read
before you see it, because a resume that will not parse is a resume nobody
reads.

---

## Design

[DESIGN.md](DESIGN.md) covers why it is built this way: the verification gate,
the data model, why matching is deterministic rather than embedding-based, and
why the rewrite model is not trusted.

Working on the code? [`.claude/skills/resume-builder/`](.claude/skills/resume-builder/SKILL.md)
holds the conventions — the rules that cannot be broken and what to run before
shipping a change.
