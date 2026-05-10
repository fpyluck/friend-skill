---
name: 朋友
description: Peer consultation skill — Codex × Claude bilateral review. Mandatory during implementation planning phases; in work phase when context is large, task is ambiguous, high-risk signal words appear, or destructive/global operations are involved. Ask the user on unclear cases; skip for simple tasks. Up to 5 rounds to consensus; user is the final arbiter. Manual trigger: /朋友, "问问 claude", "和朋友商量", "叫上朋友".
---

# Friend (朋友) — Codex × Claude Peer Consultation

You (Codex) and your local Claude Code are partners. Consult each other on important tasks; escalate to the user when stuck. **The user is the final arbiter.**

## Trigger Conditions

### Mandatory (no confirmation needed)

- **Implementation planning**: producing an action plan, architecture decision, or batch-change plan. *Pure Q&A (explain, research report) does NOT trigger.*
- **Work phase** — any of the following:
  - Context pressure (many files read, many tool calls, session feels long, approaching compression)
  - Complex or ambiguous task (multiple valid paths, unclear requirements, cross-subsystem)
  - Owner uses urgency/caution words: "critical", "important", "be careful", "don't break this" — or equivalents in any language
  - Destructive / irreversible operations (delete, migrate, production deploy)
  - Cross-repo / cross-toolchain / unclear permission boundary / global config change

### Ask the user

One sentence: "Should I loop in Claude for this?" — when you genuinely cannot judge complexity.

### Skip (don't interrupt)

Single-file change, clear fix, obviously straightforward execution.

### Manual trigger

Owner types `/朋友`, says "问问 claude", "和朋友商量", "叫上朋友" → enter consultation immediately.

### Suggest handoff

Boundary: `朋友` is for live decisions and transport; `handoff` is for durable state the next agent can resume from.

When context pressure is high or a role switch / session end is signaled, suggest: "Consider writing a handoff before switching agents — say 交班 or `/handoff`." Do not write automatically. If consultation shaped the work, say to record consensus in `decisions_and_changes` and unresolved points in `open_issues`.

## Consultation Protocol

### Marker format (critical)

**First non-blank line** must be `[FRIEND_CONSULT round=N]`, N starting at 1. Only messages starting with this token are treated as consultation — prevents accidental matches inside file content.

### Default scope: read-only advice

Consultation requests opinions only. To ask Claude to modify files directly, write explicitly: "Please directly modify: <path(s)>". Otherwise Claude gives suggestions only.

### Project context (required for round=1 of new sessions)

Include a compact context block when the task involves a local project, virtual env, container, WSL, devcontainer, remote, or monorepo. If Claude has no prior context (new session, no `session_id` to resume), always send the full block — even on logically subsequent rounds.

Principles:
- Absolute paths only. Unknown or N/A → write `N/A`.
- Commands are one-line executable strings — not descriptions like "use pytest".
- No full READMEs or configs — key file pointers only.
- Prefer activation-independent commands (absolute interpreter path, `uv run`, `docker compose exec`); shell `activate` is a fallback, valid only within the same subprocess.
- No secrets, tokens, credentials, private URLs, `.env` contents, or sensitive log fragments.

Template:
```text
## Project Context (required for round=1)
- Project root: <absolute path>
- Execution environment: <Windows PowerShell / WSL bash / Docker / devcontainer / remote / N/A>
- Project type: <language + framework>
- Virtual env: <absolute path / conda env name / container service / N/A>
- Activation command: <prefer activation-free; if needed, one-line; else N/A>
- Commands:
  - test: <one-line or N/A>
  - build: <one-line or N/A>
  - run: <one-line or N/A>
  - lint: <one-line or N/A>
- Key constraints: <2–3 items; N/A if none>
- Key file references: <@ references or absolute paths; N/A if none>
```

### Round 1: initiating consultation (Codex → Claude)

Prefer `claude_cli` direct connection: check pending and failure cache first. If clear and `claude -p` is available, use this command. If not, degrade to file mailbox. Do not temporarily override `ANTHROPIC_BASE_URL` or hardcode a local gateway; use a known working endpoint only if the owner explicitly provides one.

```bash
claude -p --output-format json \
  --add-dir "<task_dir>" \
  --allowedTools=Read,Grep,Glob,LS \
  - <<'EOF'
[FRIEND_CONSULT round=1]

Phase: PLAN  # or WORK
Task: <owner's request in brief>

## Project Context (required for round=1)
<fill from the Project Context template above>

My draft:
<plan / approach / key decisions / known facts>

Review points:
1. Any gaps, errors, or better approaches?
2. Risks I haven't considered?
3. Decision: AGREE / REFINE / OBJECT
EOF
```

Notes:
- Omit `--add-dir` and `--allowedTools` when Claude does not need local file access.
- Use one or more `--add-dir <dir>` to grant read access; default is read-only advice, not file writes.
- Parse `result` from the JSON response; retain `session_id` for multi-round continuation: `claude -p --resume <session_id> --output-format json --add-dir <dir>` (verify exact form with `claude --help`).
- If `session_id` is unavailable, start a new session with the previous round's key points, or fall back to mailbox.
- On non-zero exit, connection error, or timeout: retry once with corrected params. Do not loop-retry auth errors — degrade to manual or escalate to user.

### Manual fallback: file mailbox

When `claude_cli` is unavailable:

| Step | You (Codex) | User | Claude |
|---|---|---|---|
| 1 | Write message (with `[FRIEND_CONSULT round=N]` + full content) to `~/.shared/friend/codex_to_claude.md` | Tell Claude the path | Claude reads, replies per anti-recursion rules, writes to `~/.shared/friend/claude_to_codex.md` |
| 2 | Read `~/.shared/friend/claude_to_codex.md` after user relays | Tell you the path | — |

After writing, if no auto-dispatch is available, start `friend_mailbox_bridge.py --wait-reply` to poll for `claude_to_codex.md`; if it times out, tell the user: "Please ask Claude to read `~/.shared/friend/codex_to_claude.md`."

**Single-instance constraint**: one bridge `--watch` process per mailbox max; clean stale lock before starting (`.bridge_watch.lock` heartbeat, stale threshold: max(3×poll, 30s)). Start bridge with: `python3 ~/.shared/friend/friend_mailbox_bridge.py --watch --mailbox ~/.shared/friend` (pass `--mailbox` explicitly; required in WSL to avoid path confusion).

**Transport layers**: bridge defaults to `--transport manual` (stdlib only, no external deps) — protocol guard + archive + `pending_for_*` state + `.bridge.pending` sentinel; **no `claude -p`**. Use `--transport claude_cli` for auto-dispatch; failures use `failure_cache` circuit-break (TTL 5–15 min by error class, env `FRIEND_BRIDGE_FAILURE_TTL_SECONDS`; backoff cap 1h).

**Pending check (mandatory)**: before starting any consultation or when the user prompts, check `.bridge.pending` or `pending_for_codex` in `.bridge_state.json`; if true, read `claude_to_codex.md` and process first.

**Queue (preferred for manual new requests)**: use `~/.shared/friend/friend_queue.py send` to generate a request ID, then `wait <request-id>` to poll for Claude's reply. Old mailbox files remain for compatibility. See `~/.shared/friend/FRIEND_QUEUE_HANDOFF.md`.

**End-to-end manual prerequisite**: a `friend_mailbox_bridge.py --watch --transport manual` process must be running (either side); it converts inbox/outbox file changes into `pending_for_*` state and the sentinel file.

### Multi-round

- **REFINE** → incorporate and continue
- **OBJECT** → same, include your rationale
- **Max 5 rounds.** Still diverging → escalate to user:

```
Peer consultation: 5 rounds without consensus.
My plan: <key points>
Claude's plan: <key points>
Core disagreement: <what differs>
Please decide.
```

### Reaching consensus (AGREE)

Prefix reply with: "Agreed with Claude:" then proceed.

## Anti-recursion (critical)

When you receive input where **the first non-blank line** is `[FRIEND_CONSULT round=N]`:
- Reply AGREE / REFINE / OBJECT
- **Allowed**: resume `claude -p` (verify exact form with `claude --help`) to deliver this verdict back to the originating session
- **Prohibited**: starting a reverse `[FRIEND_CONSULT]`; expanding scope in a resume prompt; asking the counterpart to invoke third-party tools
- Nesting boundary = "does this create a new reverse consultation chain?" (not "does this call the counterpart's CLI?")
- You may read files / run read-only commands to verify facts

## Trust Level and Permissions

### FRIEND_TRUST_LEVEL (symmetric both directions)

| Level | Codex → Claude (`claude -p` direct or via bridge) | Claude → Codex (`codex exec`) |
|---|---|---|
| **safe** | `--allowedTools Read,Grep,Glob,LS` | `--sandbox read-only` |
| **workspace** (default) | `--permission-mode acceptEdits --allowedTools Read,Grep,Glob,LS,Edit,MultiEdit,Write` | `--sandbox workspace-write` |
| **danger** | `--dangerously-skip-permissions` | `--dangerously-bypass-approvals-and-sandbox` |

`danger` requires both `FRIEND_TRUST_LEVEL=danger` **and** `FRIEND_TRUST_DANGER_ACK=I_UNDERSTAND`; otherwise bridge silently downgrades to `workspace`.

Apply the corresponding flag when calling `claude -p` directly; bridge applies it automatically in `--transport claude_cli` mode.

### FRIEND_DISPATCH_MODE (bridge `claude -p` direction only)

| Mode | Behavior |
|---|---|
| **manual** | No auto `claude -p` dispatch; protocol guard + archive only |
| **auto** (default) | Existing `failure_cache` + TTL behavior |
| **eager** | Non-auth failures: TTL × 0.5 (floor 30s); auth unchanged; `--force` is the only bypass |

Priority: CLI arg > env var > default. Legacy numeric values (`0/1/2`) map to `manual/auto/eager` with a deprecation warning; permission level always defaults to `workspace`.

Config via env var or CLI arg only; see `~/.shared/friend/trust-profile.env.example`.

## Protocol Vocabulary

- **AGREE**: accept current plan, proceed to execution
- **REFINE**: direction is right, needs specific changes
- **OBJECT**: plan is fundamentally wrong — provide alternative

Do not invent new terms. When information is missing: `REFINE: need to confirm X/Y/Z with the user first`.

When citing paths, function names, commands, or tool results, include the source (which file, which command). If unverified, say so.

## Do Not Trigger

- Pure Q&A (explain code, look up docs) → answer independently
- Owner says "don't loop in Claude" or "let me check this myself"
- Receiving a reverse `[FRIEND_CONSULT]` → see anti-recursion
- Already processing a Claude reply within an active consultation

## Sync Notification

For unilateral notification of changes affecting the counterpart's future behavior (skill, hook, global rules, memory). Not multi-round.

- First non-blank line: `[NOTIFY]`. Body must include: source, category, changed file paths, diff summary, impact, expected action, sanitized summary. **Any long-term rule change must send `[NOTIFY]`.**
- Before writing a `[NOTIFY]` to Claude's inbox, check `pending_for_claude` in `.bridge_state.json`; if true, wait for it to be processed or use the queue.
- Notify only for changes affecting judgment or capability. Not for project code, logs, cache, secrets, or tokens.
- On receiving `[NOTIFY]`: reply `ACK: received — <key points>`; evaluate and adapt locally if applicable (Codex side: usually AGENTS.md / skill). Do not blindly mirror.
- If notification reveals a real disagreement, open a `[FRIEND_CONSULT]`.

### Optional: cross-clone canonical pointer

If `~/.shared/friend/CURRENT.md` exists, read its `canonical` path before consulting. Verify repo/branch/head/dirty state with live commands — do not treat CURRENT as a fact source.

CURRENT may only contain `updated`, `canonical`, `owner`, `expires`. Before writing: if `owner != codex` and not yet expired, do not overwrite — send `[NOTIFY] request-handoff` instead. If `owner == codex` or expired: atomic temp-file + rename. Default `expires = updated + 30min`; renew both `updated` and `expires` in long sessions.
