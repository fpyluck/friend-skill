---
name: xiongdimen
description: 'Tri-agent alignment skill for Claude × Codex × Gemini. Trigger only when the user explicitly writes "兄弟们", "/xiongdimen", or "xiongdimen", or asks to bring Codex and Gemini into the same design/review loop. Uses friend internally for Claude↔Codex and Gemini as a bounded leaf reviewer.'
---

# 兄弟们 (Xiongdimen)

Use `兄弟们` for feature-level, product/UX/backend alignment, or meta-skill design where Claude, Codex, and Gemini each add distinct signal. It is heavier than `朋友`; skip it for clear single-agent work or ordinary bilateral review.

## Environment Memory

For local tool, shell, path, Gemini runner, or inter-agent runtime issues, read `%XIONGDIMEN_SHARED_ENV%` if set, otherwise `%USERPROFILE%\.shared\env\ENVIRONMENT.md` if present. Update it in place only for stable environment facts, fixes, missing tools, and user improvement suggestions; do not record task details.

## Activation Boundaries

- Manual trigger only: `兄弟们`, `/xiongdimen`, `xiongdimen`, or an explicit request to involve both Codex and Gemini.
- If `[FRIEND_CONSULT round=N]` or `[XIONGDIMEN_*]` is already active, do not start another `xiongdimen` session. Respond under the active protocol.
- The initiating agent hosts the session. If Claude receives `[FRIEND_CONSULT round=N]` with `Mode: xiongdimen`, Claude is a peer reviewer only and must not spawn a new tri-agent flow.

## Roles

- **Host**: keep scope small, choose the smallest useful quorum, synthesize the final brief.
- **Claude**: ambiguity checks, alternative framings, user-facing synthesis, risk narrative.
- **Codex**: implementation contracts, backend/API shape, repo-grounded risks, validation boundaries.
- **Gemini**: breadth, frontend/UX, multimodal/product critique. Gemini is a leaf reviewer: return findings and stop.
- **User**: final arbiter.

These roles are defaults, not cages. If the task clearly needs a different emphasis, state it in the prompt instead of adding more protocol.

## Flow

1. Decide whether `朋友` is enough. Use `兄弟们` only when Gemini's breadth/frontend/multimodal view is materially useful.
2. Build a compact context block. For non-code/meta-skill tasks: `N/A — not a code project`.
3. Ask the Claude/Codex peer through `朋友` transport with `Mode: xiongdimen`.
4. Ask Gemini with `[XIONGDIMEN_GEMINI_QUERY]`. If Gemini is unavailable, record `Gemini: BLOCKED (<reason>)` and continue.
5. Synthesize a brief decision document; do not claim consensus where a participant was blocked. If participants disagree, surface the tradeoff instead of majority-voting it away.

## Claude/Codex Peer Prompt

Use the normal `friend/SKILL.md` transport, trust, resume, and anti-recursion rules.

```text
[FRIEND_CONSULT round=1]
Mode: xiongdimen
Phase: Explore | Align | Final Review

Task: <one sentence>

## Project Context
<friend project context block, or "N/A — not a code project">

Draft:
<current plan, contracts, UI flow, or skill protocol>

Review:
1. What is wrong, brittle, or missing from your role's view?
2. What should change before implementation or publication?
3. Decision: AGREE / REFINE / OBJECT
```

Inbound `Mode: xiongdimen` response as Claude:
- Check ambiguity, user outcome, synthesis quality, hidden assumptions, and product risk.
- Return `AGREE`, `REFINE`, or `OBJECT`.
- Include what was verified, what was assumed, and open risks.
- Do not initiate outbound `朋友`, `helper`, or `xiongdimen`.

## Gemini Leaf Query

Prefer the bundled runner:

```bash
XIONGDIMEN_GEMINI="${XIONGDIMEN_GEMINI:-${CLAUDE_HOME:-$HOME/.claude}/skills/xiongdimen/scripts/gemini_leaf.py}"
${XIONGDIMEN_PYTHON:-python3} "$XIONGDIMEN_GEMINI" "<prompt>" "<project_dir_or_.>"
```

The runner sends multiline prompts through stdin (`gemini -p ""`) so Windows `cmd.exe`, Git Bash, WSL, and POSIX shells do not mangle query text. If the runner is unavailable, probe `gemini` and use Gemini CLI in plan/read-only mode. On command, auth, trust, or network failure, skip Gemini and record the reason.
If Gemini returns vague or malformed output, ask once for the same response shape; if still unusable, record `Gemini: BLOCKED (unusable output)`.

```text
[XIONGDIMEN_GEMINI_QUERY]
Task: <one sentence>
Focus: frontend | product | multimodal | meta-skill | other
Context: <only what Gemini needs>
Known constraints: <backend/API/user constraints, or N/A>

Return:
Status: READY | NEEDS_CLARIFICATION | BLOCKED
Key observations: <concise bullets>
Interface/API needs: <only if relevant>
Data or UX assumptions: <specific assumptions>
Risks: <product/UX/frontend/multimodal risks>
Open questions: <blocking questions, or N/A>
```

Accept legacy `[XIONGDIMEN_FRONTEND_QUERY]` as the same Gemini leaf query (deprecated; prefer `[XIONGDIMEN_GEMINI_QUERY]`).

## Final Brief

Use the smallest brief that captures the decision:

```markdown
[XIONGDIMEN_BRIEF]
[SPLIT: YES | NO]
# Xiongdimen Brief: <topic>

## Decision
## Role Inputs
## Interface / Contract
## Implementation + Validation
## Risks / Open Questions
```

If the task is not a feature, rename sections naturally but keep `Decision`, `Role Inputs`, and `Risks / Open Questions`.

Use `[SPLIT: YES]` only when the aligned plan is ready for file-disjoint execution by `帮手`; it authorizes `帮手` but does not auto-start it. Use `[SPLIT: NO]` for alignment-only outcomes, unresolved disagreement, blocked Gemini input, or single-owner execution.

## On-Demand Collaboration Report

Default: do not emit a process report. If the owner asks for `报告`, `/report`, `协商流程报告`, `过程复盘`, `谁提的`, `谁纠正了什么`, `改了什么`, `consultation report`, or `process report`, the host synthesizes `[COLLABORATION_REPORT]` from visible round context, role inputs, briefs, and completion notes.

Report useful deltas only:
- who proposed an adopted direction;
- who corrected or refined it;
- what changed as a result;
- final decision and unresolved risks.
- explicitly rejected options only when the rejection changed the final path.

Scope to the current task or the period since the last user request unless the owner asks for a wider range. `short` reports use at most 6 key deltas; `detail` reports use at most 12 deltas with visible rationale where useful. Do not ask Gemini to self-report the process. Do not include raw transcripts, hidden deliberation, JSONL, or long quotes. If a `交班` handoff already records the final decision, focus this report on the path to that decision instead of duplicating the handoff.
