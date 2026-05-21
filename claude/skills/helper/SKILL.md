---
name: helper
description: 'Execution Split Card for Claude × Codex after the user or an aligned 朋友/Buddys decision chooses split execution. Trigger when the user explicitly writes "帮手", "/helper", or "helper", asks to split execution, or invokes an existing [SPLIT: YES] brief. [SPLIT: YES] is authorization, not an automatic trigger.'
---

# Helper (帮手) — Execution Split Card

`帮手` turns explicit split authorization into file-disjoint execution slices. It may tighten the work card when ownership is clear; it must not replace unresolved product or architecture alignment.

## Environment Memory

For local tool, shell, path, or helper runtime issues, read `%BUDDYS_SHARED_ENV%` if set, otherwise `%XIONGDIMEN_SHARED_ENV%` if set, otherwise `%USERPROFILE%\.shared\env\ENVIRONMENT.md` if present. Update it in place only for stable environment facts, fixes, missing tools, and user improvement suggestions; do not record task details.

## Routing Boundary

- **朋友**: live bilateral decision / transport.
- **兄弟们 / Buddys**: explicit tri-agent alignment when Gemini adds useful breadth.
- **交班**: durable continuity state.
- **帮手**: explicit file-disjoint execution split.

If no `[FRIEND_BRIEF]`, `[BUDDYS_BRIEF]`, or legacy `[XIONGDIMEN_BRIEF]` with `[SPLIT: YES]` exists, the user may still authorize a split directly by providing the goal, owners, integrator, validation, and stop-if boundary. If those fields are missing, ask for the missing boundary or return to `朋友` / `兄弟们` when alignment is still unresolved.

`[SPLIT: YES]` authorizes `帮手` after the user or host invokes it; it must not auto-start a helper run just because the tag appears in context.

## Input Authorization

Accepted authorization is either a split-ready brief or a current-turn user directive with the same fields:

```text
[FRIEND_BRIEF] or [BUDDYS_BRIEF] or legacy [XIONGDIMEN_BRIEF] or USER_DIRECT
[SPLIT: YES]
goal: <one sentence>
owners: <Claude / Codex / optional external leaf helpers>
integrator: <Claude | Codex>
review-by: <originating protocol: 朋友 | 兄弟们 | user-direct>
validate: <commands or N/A>
stop-if: <overlap, shared config, changed validation, blocker>
```

A brief without `[SPLIT: YES]` is discussion-only unless the user explicitly authorizes split execution in the current turn. In that case, create the smallest equivalent work card and keep the split tag in the card context.

## Work Card

Send through the existing `朋友` transport as a normal `[FRIEND_CONSULT round=N]` message; keep `[HELPER_WORK_CARD]` as the body payload, not a stand-alone transport header. If `朋友` transport is unavailable (no active session, CLI blocked), use the same transport fallback order as `朋友`: queue → flat mailbox (`codex_to_claude.md`) → user relay.

```text
[HELPER_WORK_CARD]
source: <FRIEND_BRIEF | BUDDYS_BRIEF | XIONGDIMEN_BRIEF | USER_DIRECT>
goal: <one sentence>
mode: file-disjoint
claude: <owned paths/modules/tasks>
codex: <owned paths/modules/tasks>
integrator: <Claude | Codex>
review-by: <朋友 | 兄弟们/Buddys | user-direct>
validate: <commands or N/A>
stop-if: <overlap needed, validation changes, shared config/global behavior touched, blocker>
helpers: <optional external leaf helpers, or N/A>
```

Before launch, run the gate when available:
`python %USERPROFILE%\.shared\friend\friend_gate.py check-work-card <work-card-file>`

## Execution Rules

- Work only in assigned paths/tasks.
- Do not re-plan architecture unless a local issue blocks the assigned slice; then report the blocker and return to the user or originating protocol.
- Do not revert, reformat, or silently adjust another owner’s files.
- External helpers follow their assigned work card and are never final authority. If they find a boundary problem, they report it instead of starting a new collaboration protocol.
- If a `stop-if` condition triggers mid-execution, emit `[HELPER_COMPLETE] status: blocked` immediately — include `blocker`, `changed-paths` (list any files already modified), and `needs-from-other` — then return to `review-by` without proceeding further.

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

The integrator collects completion notes, inspects helper output before trusting it, and runs validation when feasible. Use a fresh review round only when the brief requires it or integration changes the agreed contract; otherwise the integrator may close with `[HELPER_COMPLETE]`.
