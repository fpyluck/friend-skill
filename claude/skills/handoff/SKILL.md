---
name: handoff
description: 'Project continuity handoff skill for Claude, Codex, the same agent after reset, or another collaborator. Triggers when the user writes "交班", "/handoff", or "handoff" as a standalone message or invocation, or asks for handover, 接力, resumption after context loss, role switch, or a persistent status package.'
---

# Handoff

Use this as the continuity layer beside live collaboration: `handoff` records the durable project state for whoever continues next — another agent, the same agent after a context reset, or another collaborator named by the user. Treat it as current working state, not a diary: merge new facts into the sections they change, replace stale facts, and remove details that no longer help execution.

`交班` primarily reads, verifies, and writes durable state. If verification exposes a blocking live decision or split boundary, point to `朋友`, `兄弟们`, or `帮手` instead of burying the issue in the handoff; record only concluded decisions and clear next actions here.

For local tool, shell, path, or inter-agent runtime issues, read `%BUDDYS_SHARED_ENV%` if set, otherwise `%XIONGDIMEN_SHARED_ENV%` if set, otherwise `%USERPROFILE%\.shared\env\ENVIRONMENT.md` if present. Update that file in place for stable environment facts; keep project/task continuity in handoff files, not in environment memory.

If a collaboration report was requested before handoff, record only the resulting decision deltas and visible rationale in `decisions_and_changes`; do not copy raw transcripts or full reports into the handoff.

## Workflow

1. Before writing, check bridge pending: Check `%USERPROFILE%\.shared\friend\.bridge_state.json` for `pending_for_claude`; if true, process inbox per `朋友` first.
2. Use mailbox root `%USERPROFILE%\.shared\friend`; if `CURRENT.md` has `canonical`, verify it with live commands before trusting it. CURRENT.md canonical pointer protocol follows the local `朋友` skill; verify canonical with live commands before use.
3. Default handoff path: `%USERPROFILE%\.shared\friend\handoffs\<project-key>.md`; use a stable ASCII slug as the key (e.g. `myproject-v2-refactor`). Project-local `.handoff/` is opt-in. Target agent may be Claude, Codex, the same agent for self-handoff, or a user-named collaborator when supported by the receiving workflow.
4. Use the synced template at `%USERPROFILE%\.shared\friend\handoffs\handoff-template.md`; canonical source: `%CODEX_HOME%\skills\handoff\assets\handoff-template.md` if set, otherwise `%USERPROFILE%\.codex\skills\handoff\assets\handoff-template.md`. Codex side provides a skeleton generator (`new_handoff.py`); otherwise edit the synced template directly.
5. **Writing**: keep each section concise; edit in place, never append. After material changes, refresh the sections they invalidate first — especially `current_objective`, `next_actions`, `environment_commands`, `file_map`, and failure-related `error_ledger`. If collaboration shaped the work, record consensus in `decisions_and_changes`, unresolved disagreement in `open_issues`, and only collaboration nuance in `agent_notes`. Flag tasks easier for the user (GUI login, billing, signing, approval) as `[USER-ACTION]` in `owner_review`.
   Before sharing or claiming the handoff is ready, run the read-only gate:
   `python %USERPROFILE%\.shared\friend\friend_gate.py check-handoff <handoff-path>`
   Secret-pattern hits are hard failures; structure issues are warnings to fix when they affect continuity.
6. **Reading**: first verify project root exists, git status, and key files with live commands; skip expensive/destructive/login commands and note them as unverified. Then surface all `[TODO]` and `[USER-ACTION]` items from `owner_review` to the user before continuing.
7. For ordinary project handoffs, share the handoff path. For skill/protocol changes, prefer direct install or realtime reload request; use `[NOTIFY]` only as a last resort when direct install is out of scope and realtime contact is unavailable.

## Required Handoff Sections

Keep these canonical handoff sections current:

- `current_objective`
- `next_actions`
- `environment_commands`
- `file_map`
- `error_ledger`
- `decisions_and_changes`
- `open_issues`
- `agent_notes`
- `owner_review`

## Quality Rules

- Use absolute paths and one-line executable commands.
- Write `N/A` for unknowns; do not invent facts from stale context.
- Do not include secrets, tokens, `.env` contents, private query strings, or personal data.
- Verify project root, git status, and key files with live commands before writing; list unverifiable items (login, expensive ops) under `Unverified`.

## Language Adaptation

Detect the output language from an explicit owner request first, then the handoff trigger phrase or first message in the session. Default to English if ambiguous.
Write free-form prose, summaries, decisions, issue descriptions, and action descriptions in the detected language.
Keep the handoff protocol surface in English: frontmatter keys, Markdown section headers, fixed template field labels (`Background:`, `Goal:`, `Last verified:`, `For Codex:`, etc.), table headers, owner_review tags, agent names, paths, commands, and `N/A`.
Do not localize or restructure the canonical template anchors.

## owner_review tags

| Tag | Meaning | AI behavior |
|---|---|---|
| `[TODO]` | Needs an AI to act | Surface to user, then execute |
| `[SUPPLEMENT]` | Handoff info gap | Ask user or fill from context |
| `[DONE]` | User completed it | Do not redo unless asked |
| `[USER-ACTION]` | Easier for the user | Remind user explicitly |

AI may add `[USER-ACTION]` items but must not rewrite the user's existing annotations.
