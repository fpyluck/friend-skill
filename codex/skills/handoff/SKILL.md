---
name: handoff
description: Project continuity handoff skill for Codex and Claude using the 朋友 mailbox. Use when the user asks for 交班, handoff, handover, 接力, 轮流继续同一工程, asks Codex or Claude to take over the same project, asks the same agent to resume after a context reset or continuation break, or needs a persistent status package with project background, goals, environment, file locations, solved and unsolved issues, error history, and next actions.
---

# Handoff

## Purpose

Use this as the persistence layer beside `朋友`: `朋友` handles live consultation and transport; `handoff` writes the compact project state the continuing agent needs after a break, context reset, or role switch. The continuing agent may be Claude, Codex, or the same agent after its own context reset.

Treat the handoff as current working state for the next agent, not a diary: merge new facts into the sections they change, replace stale facts, and remove details that no longer help execution.

## Workflow

1. Align the shared channel before writing:
   - Read the local `朋友` skill and the counterpart skill if present:
     `/mnt/c/Users/83233/.codex/skills/朋友/SKILL.md`
     `/mnt/c/Users/83233/.claude/skills/朋友/SKILL.md`
   - Use mailbox root `/mnt/c/Users/83233/.shared/friend` unless the active `朋友` skill says otherwise.
   - If `CURRENT.md` exists, treat `canonical` only as a pointer; enter that path and verify `pwd`, git branch/head/dirty state, and relevant files with live commands. `CURRENT.md` ownership protocol (owner/expires/atomic rename) follows the local `朋友` skill.
   - If `.bridge.pending` or `.bridge_state.json` shows pending work for this agent, resolve it according to `朋友` before overwriting any mailbox file.

2. Choose a project key before every handoff:
   - Prefer a stable ASCII slug, for example `openclaw-kb-runtime` or `endovl-release-v1`.
   - Include the human project title inside the handoff file.

3. Create or locate the handoff:
   - Default path: `/mnt/c/Users/83233/.shared/friend/handoffs/<project-key>.md`.
   - Use a repo-local `.handoff/<project-key>.md` only when the user explicitly asks or the project requires versioned handoff files.
   - Set `--target-agent` to `claude`, `codex`, or the same value as `--agent` for self-handoff.
   - To create a skeleton, run:
     ```bash
     python3 /mnt/c/Users/83233/.codex/skills/handoff/scripts/new_handoff.py --project-key <slug> --title "<project title>" --agent <codex|claude> --target-agent <codex|claude>
     ```
   - Add `--project-root <absolute-path>` when the current shell is not already in the project root.
   - Add `--project-local` only for repo-local handoffs.

4. Update the existing file by editing, merging, and replacing stale facts. Do not append a diary. Keep each section ≤5 items. Keep the handoff useful for the next agent's first 5 minutes. After material changes, refresh the sections they invalidate first, especially `current_objective`, `next_actions`, `environment_commands`, `file_map`, and failure-related `error_ledger`. If a `朋友` consultation shaped the work, record consensus in `decisions_and_changes`, unresolved disagreement in `open_issues`, and only collaboration nuance in `agent_notes`.

## Required Content

Fill the canonical template at `assets/handoff-template.md`; `new_handoff.py` syncs a readable copy to `/mnt/c/Users/83233/.shared/friend/handoffs/handoff-template.md`. Keep these nine sections current:

- `current_objective`: background, plan, target outcome, and current stopping point.
- `environment_commands`: exact paths, shell/OS, virtual env/container, run/build/test/lint commands; `Last verified` (command + result) and `Unverified` (known gaps).
- `file_map`: up to 5 important paths, each with why it matters.
- `open_issues`: blockers, new questions, risky assumptions, unresolved `朋友` disagreements, and who should decide.
- `decisions_and_changes`: up to 5 recent decisions or changes, including concluded `朋友` consensus; write the reason, not a log transcript.
- `error_ledger`: major mistakes, high-frequency errors, symptoms, root cause, fix, and prevention.
- `next_actions`: ordered, testable next steps for the receiver.
- `agent_notes`: what the continuing agent should emphasize, what a peer should review, collaboration nuance, and `External refs` for URLs/papers/specs; do not duplicate consultation consensus already recorded as decisions.
- `owner_review`: user annotations — see tag table below.

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

On reading a handoff, surface all `[TODO]` and `[USER-ACTION]` items to the user before continuing.
AI may add `[USER-ACTION]` items (GUI login, billing, signing, approval) but must not rewrite the user's existing annotations.

## Quality Rules

- Use absolute paths and one-line executable commands.
- Write `N/A` for unknowns; do not invent facts from stale context.
- Do not include secrets, tokens, `.env` contents, private query strings, personal data, or long raw logs.
- Verify project root, git status, and key files with live commands before acting; skip expensive/destructive/login commands and list them under `Unverified`.
- For ordinary project handoffs, share the handoff path with the user or counterpart; reserve `[NOTIFY]` for long-term skill/protocol changes.
