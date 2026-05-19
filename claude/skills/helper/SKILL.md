---
name: helper
description: 'Execution Split Card for Claude × Codex after a finished 朋友 or 兄弟们 brief. Trigger only when the user explicitly writes "帮手", "/helper", or "helper", or asks to split execution. [SPLIT: YES] is authorization, not an automatic trigger. Does not plan or align; routes to 朋友 first when no consensus brief exists.'
---

# Helper (帮手) — Execution Split Card

`帮手` is not a planning skill. It turns an already-approved `朋友` or `兄弟们` brief into file-disjoint execution slices.

## Environment Memory

For local tool, shell, path, or helper runtime issues, read `%XIONGDIMEN_SHARED_ENV%` if set, otherwise `%USERPROFILE%\.shared\env\ENVIRONMENT.md` if present. Update it in place only for stable environment facts, fixes, missing tools, and user improvement suggestions; do not record task details.

## Routing Boundary

- **朋友**: live bilateral decision / transport.
- **兄弟们**: explicit tri-agent alignment when Gemini adds useful breadth.
- **交班**: durable continuity state.
- **帮手**: post-consensus execution split only.

If no `[FRIEND_BRIEF]` or `[XIONGDIMEN_BRIEF]` with `[SPLIT: YES]` exists in the current task context, do not invent a split. Say: `No split-ready brief found — route to 朋友 first; use 兄弟们 only if Gemini's breadth is explicitly needed.`

`[SPLIT: YES]` authorizes `帮手` after the user or host invokes it; it must not auto-start a helper run just because the tag appears in context.

## Input Brief

Accepted authorization:

```text
[FRIEND_BRIEF] or [XIONGDIMEN_BRIEF]
[SPLIT: YES]
goal: <one sentence>
owners: <Claude / Codex / optional external leaf helpers>
integrator: <Claude | Codex>
review-by: <originating protocol: 朋友 | 兄弟们>
validate: <commands or N/A>
stop-if: <overlap, shared config, changed validation, blocker>
```

`[SPLIT: NO]` means do not use `帮手`.

## Work Card

Send through the existing `朋友` transport; do not repeat mailbox, CLI, or bridge mechanics here.

```text
[HELPER_WORK_CARD]
source: <FRIEND_BRIEF | XIONGDIMEN_BRIEF>
goal: <one sentence>
mode: file-disjoint
claude: <owned paths/modules/tasks>
codex: <owned paths/modules/tasks>
integrator: <Claude | Codex>
review-by: <朋友 | 兄弟们>
validate: <commands or N/A>
stop-if: <overlap needed, validation changes, shared config/global behavior touched, blocker>
helpers: <optional external leaf helpers, or N/A>
```

Before launch, run the gate when available:
`python %USERPROFILE%\.shared\friend\friend_gate.py check-work-card <work-card-file>`

## Execution Rules

- Work only in assigned paths/tasks.
- Do not re-plan architecture; pause and return to the originating protocol if the split is wrong.
- Do not revert, reformat, or silently adjust another owner’s files.
- External helpers are execution-only leaf helpers. They must not invoke `朋友`, `兄弟们`, `交班`, or `帮手`, and they are never final authority.

## Completion

```text
[HELPER_COMPLETE]
agent: Claude
status: done | blocked
changed-paths: <paths changed, or N/A>
validation: <command + result, or N/A>
needs-from-other: <anything required before integration, or N/A>
notes: <brief risk or handoff note, or N/A>
```

The integrator collects completion notes, inspects helper output before trusting it, runs validation when feasible, then returns the review packet to `review-by`. That review is terminal acceptance only: no new split may be emitted from this helper return. `帮手` itself does not open new planning or consultation rounds.
