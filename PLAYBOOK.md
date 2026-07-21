# The Playbook

The plain-language guide. No jargon, no code knowledge assumed. If you only
read one document, read this one. (The technical version of *why* is in
[DESIGN.md](DESIGN.md); the reference manual is [README.md](README.md).)

---

## The idea in three sentences

You own two files: one lists **everything you have ever done**, the other says
**who you are and how the page should look**. Everything else — old resumes,
AI chat history, code projects — exists to help fill those two files, and
every tool asks you to check its work before anything counts. When a job
posting appears, one command turns the checked parts into a one-page resume
aimed at it.

---

## The map

Every file you will ever touch, and what touching it does:

| File | What it is | You edit it? |
|---|---|---|
| `data/experiences.yaml` | Your career, one entry per accomplishment | **Yes — this is the main one** |
| `config/resume-config.yaml` | Name, contact, job history, fonts, colours | **Yes — once, then rarely** |
| `jd/<company>.md` | A job posting you pasted in | Yes — one per application |
| `config/mining.yaml` | Words that count as "work" in your field | Yes, if your field changes |
| `config/synonyms.yaml` | Words that mean the same thing (catalog ≈ glossary) | Sometimes |
| `work/confirm.md` | Checklist: tick what's true | **Yes — tick boxes** |
| `work/mined-*.yaml` | Things the miners found for you to review | Read, copy the true ones |
| `output/<company>.docx` | The resume you send | No — regenerate instead |
| `output/<company>-gaps.md` | What the posting wanted that you can't back up | Read it |
| `lineage/<company>.md` | Where every line on the page came from | Read if curious |

Everything personal (your experiences, config, outputs, chat exports) stays
on your machine — it is never uploaded when the code is shared.

---

## Words this project uses

- **Experience** — one thing you did, written in your words, in past tense.
  *"Chaired the data governance council"* is one experience.
- **Confirmed** — you have said "this is true and I would defend it in an
  interview." **Only confirmed experiences can ever appear on a resume.**
  Everything arrives unconfirmed; confirming is always a human act.
- **Tier** — where an experience came from, strongest first:
  `sent-resume` (a resume you actually sent) → `interviewed` (you said it
  aloud to this tool) → `chat-corroborated` (you typed it to an AI while
  working) → `repo` (a code project of yours) → `agent-log` (an AI's notes
  about a session with you) → `draft-pack` (an AI wrote it; verify hardest).
- **Tags** — the search words that let a posting find an experience.
- **Metric** — a number. Each is `measured` (it happened), `target` (you
  aimed for it), or `unknown` (decide before it ships). A target is never
  printed as an achievement.
- **JD** — job description. Lives in `jd/`, with the company, role, and
  requisition number at the top.
- **Gap** — something a posting wants that nothing confirmed covers. Gaps are
  reported, never papered over.
- **Candidate** — something a miner found that *might* be an experience.
  Candidates wait in `work/` until you promote them.
- **The gate** — the rule holding all of it together: unconfirmed content is
  never even loaded, so no bug and no model can leak it onto a page.

---

## Recipes

### "I found a job posting"

1. Copy the posting text into `jd/company.md`, with facts at the top:
   ```
   ---
   company: Acme Corporation
   role: Director, Data Governance
   req: R-12345
   closes: 2026-09-06
   ---
   (posting text pasted below)
   ```
2. `python propose.py jd/company.md` — see what matches, what *would* match
   if you confirmed it, and what's missing.
3. `python run.py jd/company.md` — build the resume.
4. Read `output/company-gaps.md` before sending. It's the honest list of
   what the posting wanted that you can't back up.

### "The tool says I have gaps"

`python interview.py jd/company.md`

It asks about each gap, in order of how much the posting cares: shows you the
posting's own sentence, shows the nearest thing already in your library (often
the answer is "confirm that one"), then asks whether you did work like this.
**Type your answer in past tense; it is saved word-for-word as yours.** Press
Enter to skip anything — a skipped gap stays a gap, which is the truthful
outcome. Nothing is ever suggested to you, and no number is ever proposed.

### "I want my AI chat history working for me"

- ChatGPT: Settings → Data controls → Export. Unzip into `export/`.
- Claude (claude.ai): Settings → Privacy → Export data. The link arrives by
  email; unzip into `export/`.
- Claude Code (this tool): already on your disk —
  `python mine_chat.py --pull-claude` copies it in, skipping its own
  resume-building sessions so the resume can't cite itself.
- Then: `python mine_chat.py --jd jd/company.md` to aim it at a posting, or
  plain `python mine_chat.py` for everything.

What comes back (`work/mined-candidates.yaml`) is **sentences you yourself
typed** that claim completed work — "Created…", "Automated…", "I
spearheaded…" — each with the conversation, the date, and how strong the
evidence is that it actually shipped. Copy the true ones into
`data/experiences.yaml`, tidy the wording, set `confirmed: true`.

### "I have code projects that prove skills"

`python mine_repos.py --agent-notes`

Scans your local git repos (including the Antigravity workspace) and your
IDE agent's session notes. **Warning it will keep repeating: READMEs and
agent notes are usually written by an AI**, so everything it finds is a lead
to verify, not your words yet. Rewrite before confirming.

### "There's a pile of unconfirmed stuff — what's worth my time?"

1. `python propose.py jd/company.md` — ranks locked experiences by value
   *for that posting*.
2. `python confirm.py` — opens the master checklist, grouped by job, worst
   evidence flagged. Tick what's true.
3. `python confirm.py --apply` — carries your ticks back. Backup is automatic.

### "I just finished something at work" *(the habit that compounds)*

Open `data/experiences.yaml`, copy any entry as a template, four minutes:

```yaml
- id: acme-lineage-rollout
  job: acme
  confirmed: true
  tier: sent-resume
  tags: [data lineage, impact analysis]
  metrics:
    - value: "12 sources"
      kind: measured
  text:
    long: "Delivered end-to-end lineage across 12 upstream sources."
```

Three years later that number is still there, measured while you still knew it.

---

## Rules the tools live by (and you should too when editing)

1. **Past tense, your words.** "Led the rollout", not "responsible for rollout".
2. **No number you didn't measure.** No number is always acceptable; an
   invented one never is.
3. **A target is a target.** If you aimed at 95% and never measured the
   result, mark it `target` — it prints as a criterion you set, not a win.
4. **Don't inflate the verb.** If you helped, write helped. The tools reject
   AI rewrites that promote "helped" to "led" — extend yourself the same
   courtesy.
5. **When unsure, leave it unconfirmed.** Unconfirmed costs you nothing —
   it just waits. A false line on a resume costs you the interview.
