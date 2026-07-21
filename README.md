# resume-builder

A resume generator that makes you prove your own claims before it will print them.

## The idea

Most resume tools take your existing resume and reword it for a job posting. They
assume everything already on it is true.

This one doesn't. Every accomplishment starts unconfirmed. You tick a box to confirm
it. **Anything you haven't ticked cannot appear in the finished document** — not
because the tool politely avoids it, but because the code never reads it.

That check is the whole point. The reason resumes drift into fiction isn't bad
intent, it's that a plausible sentence written six drafts ago becomes something you
have to defend in an interview.

## How it works

```
your old resumes  ─┐
                   ├─►  master-resume.md   ──►  tailored one-page .docx
draft claims      ─┘    (you tick boxes)         (only ticked lines)
```

1. **Collect** — reads your old resumes, pulls out every accomplishment, merges
   duplicates, and flags places where two resumes told the same story differently.
2. **Confirm** — you get one checklist file. Tick what's true, fix the wording,
   delete what isn't. This is the only manual step, and it's the important one.
3. **Tailor** — drop in a job posting. The tool scores each confirmed accomplishment
   against it, keeps the best, and writes a one-page Word document.

## Using it

```bash
pip install python-docx

python ingest.py                  # read old resumes
python build_master.py            # build the checklist
#    ... open master-resume.md and tick boxes ...
python run.py jd/acme.md          # posting in, resume out
```

You get three files per application:

| File | What it's for |
|---|---|
| `output/acme.docx` | The resume you send |
| `output/acme-gaps.md` | What the job wanted that you can't back up |
| `lineage/acme.md` | Where every line came from |

Re-run any time. **Your ticked boxes are preserved** when the checklist rebuilds.

## What it does that's unusual

**It reads the seniority of the posting.** A VP posting and a team-lead posting get
different framing of the *same* facts — which ones lead, which compress, and whether
you "directed" or "built" something. It never changes what happened, only which true
thing goes first.

**It tells you when you're not qualified.** Every resume gets an ATS score out of
100. Below 70, it lists the job's key terms that nothing in your history matches.
That's a real gap in your experience, not a wording problem, and the tool will not
invent anything to close it.

**It never makes up a number.** If a bullet has no metric, it asks you what the
number was. It won't suggest one, estimate a range, or offer a default. If you don't
remember, the line ships without a number — that's a normal outcome, not a failure.

**It won't turn a goal into an achievement.** For every number you do provide, it
asks one question: was that measured, or was it the target you set? Targets get
written as "established criteria of X" — never as something you hit.

**It's free to run.** No AI model is called when generating a resume. It's ordinary
matching code, so each application costs nothing.

## Files

| File | Job |
|---|---|
| `ingest.py` | Old resumes → plain text, flags conflicting versions |
| `build_master.py` | Builds the checklist, keeps your edits |
| `tailor.py` | Scores against a posting, writes the .docx |
| `run.py` | Does all of the above in one command |
| `track.py` | Logs each application to a spreadsheet |
| `mine_chat.py` | Optional: mines a ChatGPT export for forgotten work |
| `config/synonyms.yaml` | Word equivalents, edit freely |

### About `mine_chat.py`

If you've spent years discussing your work with a chatbot, that history is a diary
you didn't know you were keeping. This grades what it finds by how strong the
evidence is: asking *how to do* something is weak, pasting a config file is stronger,
pasting an error message from a live system is strongest. It also refuses to read
your resume-writing sessions — those are full of resume language, and treating them
as proof would just be the resume agreeing with itself.

Still just candidates. You confirm them like everything else.

## Not built yet

Cover letters, reading postings from a URL, and autofilling applications.

## Note

Output is single-column with plain headings and no tables or text boxes, because
applicant tracking systems mangle anything fancier. Every generated file is re-opened
and re-read before you see it — a resume that won't parse is a resume nobody reads.
