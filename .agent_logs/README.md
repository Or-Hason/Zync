# Agent failure archive

One file per hard-won investigation, named `YYYY-MM-DD_TaskName.md`.

These record **what did not work and why** — the expensive half of debugging, which
leaves no trace in the code or in git history because failed approaches get deleted
before they are ever committed. Without this, the same dead ends get re-explored months
later by whoever inherits the problem.

Tracked in git on purpose: the value is entirely in surviving to the next person and the
next clone, and GitHub issues link to these files by path. Contrast with `sync.md`, which
is transient per-session state and is gitignored.

## What belongs here

- Approaches that failed, with the reason they cannot work — not just that they failed.
- Evidence that settles a question (vendored source, an upstream issue, a measurement).
- Traps that make a correct fix *look* broken.

## What does not

- Work diaries or changelogs — git history covers those.
- Anything the code should explain about itself. That belongs in a comment next to it.
