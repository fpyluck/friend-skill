---
name: handoff
description: 'Project continuity handoff companion for Claude and Codex 朋友 collaboration. Triggers when user writes "交班", "/handoff", or "handoff" as a standalone message or invocation, or asks for handover, 接力, 轮流继续同一工程, asks Claude to take over from Codex or prepare work for Codex, asks the same agent to resume after a context reset or continuation break, or needs a persistent project status package.'
---

# Handoff

Use this as the continuity layer beside `朋友`: `朋友` handles live consultation and transport; `handoff` records the durable project state for whoever continues next — another agent or the same agent after a context reset. Treat it as current working state, not a diary: merge new facts into the sections they change, replace stale facts, and remove details that no longer help execution.

`交班` does not invoke `朋友`, `兄弟们`, or `帮手`; it only reads, verifies, and writes durable state. If a live decision or split is needed, finish that protocol first and record the result here.

For local tool, shell, path, or inter-agent runtime issues, read `%XIONGDIMEN_SHARED_ENV%` if set, otherwise `%USERPROFILE%\.shared\env\ENVIRONMENT.md` if present. Update that file in place for stable environment facts; keep project/task continuity in handoff files, not in environment memory.

If a collaboration report was requested before handoff, record only the resulting decision deltas and visible rationale in `decisions_and_changes`; do not copy raw transcripts or full reports into the handoff.

## Workflow

1. Before writing, check bridge pending and align with `朋友`:
   - Check `%USERPROFILE%\.shared\friend\.bridge.pending` or `.bridge_state.json` for `pending_for_claude`; if true, process inbox per `朋友` first.
   - Read local `朋友` skills if present: `%USERPROFILE%\.claude\skills\friend\SKILL.md`, `%USERPROFILE%\.codex\skills\friend\SKILL.md`
2. Use mailbox root `%USERPROFILE%\.shared\friend`; if `CURRENT.md` has `canonical`, verify it with live commands before trusting it. CURRENT.md canonical pointer protocol follows the local `朋友` skill; verify canonical with live commands before use.
3. Default handoff path: `%USERPROFILE%\.shared\friend\handoffs\<project-key>.md`; use a stable ASCII slug as the key (e.g. `myproject-v2-refactor`). Project-local `.handoff/` is opt-in. Target agent may be Claude, Codex, or the same agent for self-handoff.
4. Use the synced template at `%USERPROFILE%\.shared\friend\handoffs\handoff-template.md`; canonical source: `%USERPROFILE%\.codex\skills\handoff\assets\handoff-template.md`. Codex side provides a skeleton generator (`new_handoff.py`); otherwise edit the synced template directly.
5. **Writing**: keep each section ≤5 items; edit in place, never append. After material changes, refresh the sections they invalidate first — especially `current_objective`, `next_actions`, `environment_commands`, `file_map`, and failure-related `error_ledger`. If `朋友` shaped the work, record consensus in `decisions_and_changes`, unresolved disagreement in `open_issues`, and only collaboration nuance in `agent_notes`. Flag tasks easier for the user (GUI login, billing, signing, approval) as `[USER-ACTION]` in `owner_review`.
   Before sharing or claiming the handoff is ready, run the read-only gate:
   `python %USERPROFILE%\.shared\friend\friend_gate.py check-handoff <handoff-path>`
   Secret-pattern hits are hard failures; structure issues are warnings to fix when they affect continuity.
6. **Reading**: first verify project root exists, git status, and key files with live commands; skip expensive/destructive/login commands and note them as unverified. Then surface all `[TODO]` and `[USER-ACTION]` items from `owner_review` to the user before continuing.
7. For ordinary project handoffs, share the handoff path. For skill/protocol changes, prefer direct install or realtime reload request; use `[NOTIFY]` only as a last resort when direct install is out of scope and realtime contact is unavailable.

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
