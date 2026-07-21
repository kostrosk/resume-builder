# resume-builder

A resume generator that makes you prove your own claims before it will print them.

## The idea

Most resume tools take your existing resume and reword it for a job posting. They
assume everything on it is already true.

This one doesn't. Every accomplishment starts unconfirmed. You mark it true once,
and **anything unconfirmed cannot appear in the finished document** — not because
the tool politely avoids it, but because the code never loads it in the first place.

## Who it's for

Two kinds of people, and the second is the point.

**Job hunting now.** You have six versions of your resume in a folder, each half
true and none current. Point this at them once and you get a single library of
everything you've done, deduplicated, with the conflicts flagged for you to settle.

**Employed and staying ready.** The hard part of a resume isn't writing it, it's
remembering. Finish something good on a Thursday, add four lines to
`data/experiences.yaml`, and it's there years later when you need it — with the
number you actually measured, while you still remember it. The library grows as
your career does. When a posting appears, the resume is a command, not a weekend.

## How it's put together

Three files you edit. No code, ever.

```
data/experiences.yaml     everything you've ever done, written once
config/resume-config.yaml where you worked + how the page should look
jd/whatever.md            the job posting you're applying to
                                    │
                                    ▼
                          output/whatever.docx
```

**`data/experiences.yaml` — your experience library.** One entry per
accomplishment. Each carries the wording you approved, the tags a job posting can
find it by, and any numbers with a note on whether each was a *measured result* or
a *target you set*. Write an experience once; it's available to every resume you
ever generate.

**`config/resume-config.yaml` — the builder.** Your job history (company, ticker,
role, dates), which sections appear and in what order, and the full visual style —
fonts, sizes, colours, margins, spacing. Add a job entry and its experiences appear
automatically. Reorder the sections list and the page reorders.

**`jd/` — the posting.** Paste it in as a text file.

Because these are separate, one library of experiences produces unlimited resume
variations. Change a date, hide a job, reorder sections, drop a section entirely —
you never touch an experience, and you never touch code.

## Using it

```bash
pip install python-docx pyyaml

cp config/resume-config.example.yaml config/resume-config.yaml
#   ... fill in your name, links, and jobs ...

python migrate.py                 # first time only — imports your old resumes
python propose.py jd/acme.md      # what should go on this resume, and why
python run.py jd/acme.md          # posting in, resume out
```

Your `config/resume-config.yaml` and `data/experiences.yaml` are both gitignored,
so your phone number and career history never leave your machine even if you fork
this publicly.

You get:

| File | What it's for |
|---|---|
| `output/acme.docx` | The resume you send |
| `output/acme-gaps.md` | What the job wanted that you can't back up |
| `output/acme-rewrites.md` | Every shortened bullet, original beside it |
| `lineage/acme.md` | Where every line came from |

## Writing an experience

```yaml
- id: acme-dg-charter
  job: acme                       # matches an id in resume-config.yaml
  confirmed: true                 # false = invisible to the builder
  tags: [data governance, council, roadmap, operating model]
  metrics:
    - value: "10%"
      kind: measured              # measured | target | unknown
      context: reduction in data debt
  text:
    long: "Chartered a data governance program and **roadmap**; chaired
           biweekly councils and working groups."
```

`tags` is how a posting finds this experience — think of them as the words a
recruiter would search for. `**bold**` and `*italic*` work inside any text and come
through as real formatting in Word.

`kind: target` means you set that number as a goal, not that you hit it. Those get
written as "established criteria of X" and never as an achievement.

### Tuning what gets picked

Four optional knobs on any experience, when the automatic match gets it wrong:

```yaml
match:   [operating model, decision rights]   # extra keywords, weighted highest
boost:   1.5        # multiply this one's score
pin:     true       # always include it, whatever the posting says
exclude: true       # never include it
```

## Deciding what to add: `propose.py`

```bash
python propose.py jd/acme.md
```

This reads the posting and writes you a worksheet answering three questions:

1. **Which experiences already match**, and which words earned the match
2. **Which experiences would match but aren't confirmed** — the ones you're sitting
   on without knowing it
3. **Which words the posting cares about that you cover nowhere** — with the nearest
   experience you have, and the exact `match:` line to add if it genuinely applies

That last part is the honest bit. It suggests a keyword only alongside the
experience it would attach to, so you're deciding whether something is *true*, not
whether a word would help. If nothing of yours is close, it says so and moves on.

`propose.py` changes no files. It proposes; you edit.

## What it does that's unusual

**It reads the seniority of the posting.** A VP posting and a team-lead posting get
different framing of the *same* facts — which lead, which compress, and which verb
describes the work. It never changes what happened, only what goes first.

**It tells you when you're not qualified.** Every resume gets an ATS score out of
100. Below 70, it lists the posting's key terms that nothing in your history
matches. That's a real gap, not a wording problem, and the tool will not invent
anything to close it.

**It never makes up a number.** If a bullet has no metric, it stays without one.
The tool won't suggest, estimate, or default a value.

**Skills are checked against the body.** A skill only prints if it also appears in a
bullet that shipped, so the skills line can't claim something the resume doesn't
support.

**It's free to run.** Generating a resume calls no AI model. Ordinary matching code,
so each application costs nothing.

## The AI rewrite (optional)

Long bullets have to be shortened to fit one page. `--llm` lets a model do that:

```bash
python run.py jd/acme.md --llm
```

**The model is not trusted.** Every rewrite it returns is checked afterwards by
ordinary code, and thrown away if it:

- introduces a number that wasn't in your original
- introduces a tool, company, or system name that wasn't in your original
- strengthens the claim — "helped" may not become "led", "designed" may not
  become "implemented"
- comes back longer than what it replaced

A rejected rewrite falls back to simply cutting the sentence short at a natural
break, which invents nothing. Every rewrite that ships lands in
`output/<job>-rewrites.md` with your original beside it, so you can read exactly
what changed before you send anything.

Without `--llm`, no model runs at all.

## Files

| File | Job |
|---|---|
| `migrate.py` | One-time import of old resumes into the library |
| `propose.py` | Reads a posting, tells you what to add and why |
| `tailor.py` | Matches a posting, picks bullets, scores the result |
| `test_guardrails.py` | Proves the AI rewrite checks actually block bad rewrites |
| `render.py` | Turns the result into a styled Word document |
| `run.py` | Does all of it in one command |
| `track.py` | Logs each application to a spreadsheet |
| `ingest.py` | Reads .docx resumes into plain text |
| `mine_chat.py` | Optional: mines a ChatGPT export for forgotten work |
| `config/synonyms.yaml` | Word equivalents, edit freely |

### About `mine_chat.py`

If you've spent years discussing your work with a chatbot, that history is a diary
you didn't know you were keeping. It grades what it finds by evidence strength:
asking *how to do* something is weak, pasting a config file is stronger, pasting an
error from a live system is strongest. It also refuses to read your resume-writing
sessions — those are full of resume language, and treating them as proof would just
be the resume agreeing with itself.

Still only candidates. You confirm them like everything else.

## Not built yet

Cover letters, reading postings from a URL, and autofilling applications.

## A note on the output

Single column, plain headings, no tables, no text boxes, no headers or footers —
applicant tracking systems mangle anything fancier. Every generated file is
re-opened and re-read before you see it, because a resume that won't parse is a
resume nobody reads.
