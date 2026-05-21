---
name: buddys
description: 'Buddys tri-agent alignment skill for Claude × Codex × Gemini. Trigger when the user explicitly writes "兄弟们", "/buddys", "buddys", or legacy "/xiongdimen" / "xiongdimen", or asks to bring Codex and Gemini into the same design/review loop. Uses friend internally as Claude↔Codex transport and asks Gemini for bounded independent review.'
---

# 兄弟们 (Buddys)

Use `兄弟们` / `Buddys` when Claude, Codex, and Gemini can add distinct signal to the same decision. It is heavier than `朋友`; skip it when the goal is clear enough for one agent or ordinary bilateral review.

## Environment Memory

For local tool, shell, path, Gemini runner, or inter-agent runtime issues, read `%BUDDYS_SHARED_ENV%` if set, otherwise `%XIONGDIMEN_SHARED_ENV%` if set, otherwise `%USERPROFILE%\.shared\env\ENVIRONMENT.md` if present. Update it in place only for stable environment facts, fixes, missing tools, and user improvement suggestions; do not record task details.

## Activation Boundaries

- Manual trigger: `兄弟们`, `/buddys`, `buddys`, legacy `/xiongdimen` / `xiongdimen`, or an explicit request to involve both Codex and Gemini. `朋友` may recommend escalating to `兄弟们`, but `兄弟们` does not auto-start.
- If `[FRIEND_CONSULT round=N]`, `[BUDDYS_*]`, or legacy `[XIONGDIMEN_*]` is already active, do not start another Buddys session. Respond under the active protocol.
- The initiating agent hosts the session. If Claude receives `[FRIEND_CONSULT round=N]` with `Mode: buddys` or legacy `Mode: xiongdimen`, Claude responds within that inbound flow and must not spawn a new tri-agent flow.

## Roles

- **Host**: keep scope useful, choose the smallest useful quorum, synthesize the final brief.
- **Claude**: ambiguity checks, alternative framings, user-facing synthesis, risk narrative.
- **Codex**: implementation contracts, backend/API shape, repo-grounded risks, validation boundaries.
- **Gemini**: breadth, frontend/UX, multimodal/product critique, or any outcome-changing issue the prompt asks it to inspect.
- **User**: final arbiter.

These roles are defaults, not cages. Any participant may raise out-of-role issues when they change the decision. The host owns synthesis, scope control, and whether follow-up rounds are worth the cost.

## Flow

1. Decide whether `朋友` is enough. Use `兄弟们` only when a third independent view is materially useful.
2. Build a compact context block. For non-code/meta-skill tasks: `N/A — not a code project`.
3. Ask the Claude/Codex peer through `朋友` transport with `Mode: buddys`. This is internal transport for Buddys, not a separate user-facing `朋友` activation.
4. Ask Gemini with `[BUDDYS_GEMINI_QUERY]`. If Gemini is unavailable, record `Gemini: BLOCKED (<reason>)` in the brief's `participants` field and continue with the two-agent consensus.
5. Synthesize a brief decision document; do not claim consensus where a participant was blocked. Always include the `participants` status line in the brief so downstream agents know the quorum. If participants disagree, surface the tradeoff instead of majority-voting it away.

## Claude/Codex Peer Prompt

Use the normal `friend/SKILL.md` transport, trust, resume, and anti-recursion rules.

```text
[FRIEND_CONSULT round=1]
Mode: buddys
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

Inbound `Mode: buddys` or legacy `Mode: xiongdimen` response as Claude:
- Check ambiguity, user outcome, synthesis quality, hidden assumptions, and product risk.
- Return `AGREE`, `REFINE`, or `OBJECT`.
- Include what was verified, what was assumed, and open risks.
- Do not start a new outbound collaboration chain from inside this inbound review.

## Gemini Query

Prefer the bundled runner:

```bash
BUDDYS_GEMINI="${BUDDYS_GEMINI:-${XIONGDIMEN_GEMINI:-${CLAUDE_HOME:-$HOME/.claude}/skills/xiongdimen/scripts/gemini_leaf.py}}"
${BUDDYS_PYTHON:-${XIONGDIMEN_PYTHON:-python3}} "$BUDDYS_GEMINI" "<prompt>" "<project_dir_or_.>"
```

The runner sends multiline prompts through stdin (`gemini -p ""`) so Windows `cmd.exe`, Git Bash, WSL, and POSIX shells do not mangle query text. If the runner is unavailable, probe `gemini` and use Gemini CLI in plan/read-only mode. On command, auth, trust, or network failure, skip Gemini and record the reason.
Gemini is bounded by the prompt and does not own final synthesis. It may raise out-of-focus issues, propose alternatives, or answer follow-up rounds when useful. If Gemini returns vague or malformed output, request the same response shape again while it is still useful; record `Gemini: BLOCKED (unusable output)` when the output cannot support synthesis.

```text
[BUDDYS_GEMINI_QUERY]
Task: <one sentence>
Focus: frontend | product | multimodal | meta-skill | other
Context: <only what Gemini needs>
Known constraints: <backend/API/user constraints, or N/A>

Return:
Status: READY | NEEDS_CLARIFICATION | BLOCKED
Key observations: <concise bullets>
Interface/API needs: <only if relevant>
Data or UX assumptions: <specific assumptions>
Risks: <risks relevant to the requested focus>
Open questions: <blocking questions, or N/A>
```

Accept legacy `[XIONGDIMEN_GEMINI_QUERY]` and `[XIONGDIMEN_FRONTEND_QUERY]` as the same Gemini leaf query.

New briefs and work cards output `BUDDYS_*` markers only; `XIONGDIMEN_*` is accepted as input for backward compatibility but never emitted.

## Final Brief

Use the smallest brief that captures the decision:

```markdown
[BUDDYS_BRIEF]
# Buddys Brief: <topic>
participants: Claude: READY | Codex: READY | Gemini: READY|BLOCKED(<reason>)

## Decision
## Role Inputs
## Interface / Contract
## Implementation + Validation
## Risks / Open Questions
```

If the task is not a feature, rename sections naturally but keep `Decision`, `Role Inputs`, and `Risks / Open Questions`.

When the owner asks for split execution or the aligned decision explicitly needs file-disjoint execution by `帮手`, add `[SPLIT: YES]` to the brief with owners, integrator, validation, and stop-if fields. The tag remains explicit authorization; discussion-only outcomes omit it.

## Suggest handoff

When context pressure is high, a role switch is signaled, or the session is ending after a tri-agent decision, suggest: "Consider writing a handoff before switching agents — say 交班 or `/handoff`." Do not write automatically. Record consensus in `decisions_and_changes` and unresolved points in `open_issues`.

## On-Demand Collaboration Report

Default: do not emit a process report. If the owner asks for `报告`, `/report`, `协商流程报告`, `过程复盘`, `谁提的`, `谁纠正了什么`, `改了什么`, `consultation report`, or `process report`, the host synthesizes `[COLLABORATION_REPORT]` from visible round context, role inputs, briefs, and completion notes.

Report useful deltas only:
- who proposed an adopted direction;
- who corrected or refined it;
- what changed as a result;
- final decision and unresolved risks.
- explicitly rejected options only when the rejection changed the final path.

Scope to the current task or the period since the last user request unless the owner asks for a wider range. Use `short` for key deltas; use `detail` when visible rationale is useful. Do not ask Gemini to self-report the process. Do not include raw transcripts, hidden deliberation, JSONL, or long quotes. If a `交班` handoff already records the final decision, focus this report on the path to that decision instead of duplicating the handoff.
