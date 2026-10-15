# Issue tracker: Local Markdown

Issues and specs for this repo live as markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The spec is `.scratch/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`, never a single combined tickets file
- Triage state is recorded as a `Status:` line near the top of each issue file (see `triage-labels.md` for the role strings)
- Comments and conversation history append to the bottom of the file under a `## Comments` heading

## When a skill says "publish to the issue tracker"

Create a new file under `.scratch/<feature-slug>/` (creating the directory if needed).

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** file per ticket.

- **Map**: `.scratch/<effort>/map.md` (the Notes / Decisions-so-far / Fog body).
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`, with the question in the body. A `Type:` line records the ticket type (`research`/`prototype`/`grilling`/`task`); a `Status:` line records `claimed`/`resolved`.
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`.
- **Frontier**: scan `.scratch/<effort>/issues/` for files that are open, unblocked, and unclaimed; first by number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under an `## Answer` heading, set `Status: resolved`, then append a context pointer (gist + link) to the map's Decisions-so-far in `map.md`.

## Lifecycle (repo-specific addition)

A ticket is **not done when the code is done**. Closing requires distillation:

- Durable knowledge (semantics, gotchas, baselines, hardware facts that a fresh session cannot cheaply regenerate) graduates into `docs/` or a new ADR.
- Capability/status conclusions update `STATUS.md`.
- The narrative (conversation record, superseded designs) moves to `archive/<unit>/`, one directory per archiving event, indexed in `archive/INDEX.md`.

Closing also requires the doc gate to be green: run `scripts/doc_gate.sh` — **errors must be zero** before the ticket resolves (fix or open a follow-up ticket); warnings are recorded in the closing reply, not blocking. Placement rules for any `.md` written along the way: `skills/doc-writing/SKILL.md` (four-question decision tree; enforced at write time by the `doc_write_gate` hook).

The reviewer treats missing distillation as a diff defect.
