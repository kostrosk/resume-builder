---
name: ship-decision
description: Close the loop on any decision, agreement, or change in this project so nothing lives only in chat. Captures the decision into the right durable place (DESIGN/README/PLAYBOOK/CLAUDE.md/a skill and/or persistent memory), verifies, commits, and pushes to main for HIL review. Invoke after the user approves a direction, or when you catch yourself having only said something.
---

# ship-decision — nothing lives only in the chat

The failure this prevents: a decision gets made in conversation, acted on
partway, and never written down. Next session it is gone. The user reads the
repo and their memory, not this transcript — so a decision that is not in one
of those did not really happen.

Trigger this whenever any of these is true:
- the user approved a direction, goal, or strategy ("agree", "do that", "yes")
- a hard rule or constraint was established
- a behaviour changed and the docs no longer match the code
- you notice you *said* you would remember/record something and did not

## The loop — all five, in order, every time

1. **Name the decision** in one sentence. If you cannot, it is not ready to
   ship — ask the user.

2. **Route it to the right durable home** (often more than one):

   | The decision is about… | Write it to |
   |---|---|
   | Why the product works this way | `DESIGN.md` |
   | How a user operates it | `README.md` / `PLAYBOOK.md` |
   | A rule agents must follow in this repo | `CLAUDE.md` and/or a skill |
   | A repeatable workflow | a new `.claude/skills/<name>/SKILL.md` |
   | Who the user is / an ongoing goal / feedback on how to work | persistent memory (`~/.claude/.../memory/*.md` + `MEMORY.md` index) |

   Strategy and doctrine (e.g. how ATS is beaten compliantly) are product
   reasoning → `DESIGN.md`, and the durable intent → memory. Do both.

3. **Index it.** A new skill is referenced from `README.md` and `CLAUDE.md`.
   A new memory gets a one-line pointer in `MEMORY.md`. An orphan file that
   nothing links to will not be found next time.

4. **Verify before committing:**
   ```bash
   python test_guardrails.py               # must pass all
   python run.py jd/sample-director-dg.md   # end-to-end build
   ```
   Then the privacy scan — grep every tracked file for the user's name,
   employers, target companies, and home paths (keep the pattern out of the
   repo; hold it in the session, not a committed file). A hit in a tracked
   file is a stop — replace with an Acme/placeholder. Personal data files are
   already gitignored.

5. **Commit and push to `main`** — the push *is* the HIL review artifact; the
   user reviews on GitHub. Commit message states the decision and why. Use the
   repo's trailer (GitHub noreply author; a private email will be rejected on
   push).

## Done means

The decision is now true in the repo and/or memory, verified, and on `main`.
If you only edited files but did not push, you are not done — unpushed work is
invisible to the user's review loop. If you only wrote memory but the code and
docs still contradict it, you are not done either.

## Cross-checks

- Memory is for durable intent (goals, who the user is, how to work), not for
  facts the repo already records — those go in the repo. See
  `.claude/skills/resume-builder/SKILL.md` for the hard product rules a
  decision must never violate.
