---
name: friend
description: 'Peer consultation skill — Claude × Codex bilateral review. Triggers when user writes "朋友", "/friend", or "friend" as a standalone message or invocation, or says "问问 codex", "和朋友商量", or "叫上朋友". Mandatory during implementation planning phases; in work phase when context is large, task is ambiguous, high-risk signal words appear, or destructive/global operations are involved. Ask the user on unclear cases; skip for simple tasks. Up to 5 rounds to consensus; user is the final arbiter.'
---

# Friend (朋友) — Claude × Codex Peer Consultation

You (Claude) and your local Codex are partners. Consult each other on important tasks; escalate to the user when stuck. **The user is the final arbiter.**

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

One sentence: "Should I loop in Codex for this?" — when you genuinely cannot judge complexity.

### Skip (don't interrupt)

Single-file change, clear fix, obviously straightforward execution.

### Manual trigger

Owner types `/friend`, says "问问 codex", "和朋友商量", "叫上朋友" → enter consultation immediately.

### Suggest handoff

Boundary: `朋友` is for live decisions and transport; `handoff` is for durable state the next agent can resume from.

When context pressure is high or a role switch / session end is signaled, suggest: "Consider writing a handoff before switching agents — say 交班 or `/handoff`." Do not write automatically. If consultation shaped the work, say to record consensus in `decisions_and_changes` and unresolved points in `open_issues`.

## Consultation Protocol

### Marker format (critical)

**First non-blank line** must be `[FRIEND_CONSULT round=N]`, N starting at 1. Only messages starting with this token are treated as consultation — prevents accidental matches inside file content.

### Gate preflight

Before starting a new consultation, prefer the shared read-only gate:
`python C:\Users\83233\.shared\friend\friend_gate.py --mailbox C:\Users\83233\.shared\friend status --intent friend --json`

For a prepared outbound message, check it with:
`python C:\Users\83233\.shared\friend\friend_gate.py --mailbox C:\Users\83233\.shared\friend check-consult <message-file> --recipient codex --transport <direct|queue|mailbox>`

Use the gate to catch pending mailbox state, queue depth, bridge health, failure cache, and obvious secret patterns. It does not replace the consultation protocol.

### Default scope: read-only advice

Consultation requests opinions only. To ask Codex to modify files directly, write explicitly: "Please directly modify: <path(s)>". Otherwise Codex gives suggestions only.

### Project context (required for round=1 of new sessions)

Include a compact context block when the task involves a local project, virtual env, container, WSL, devcontainer, remote, or monorepo. If Codex has no prior context (new session, no resume id to use), always send the full block — even on logically subsequent rounds.

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

### Transport (Claude → Codex direction)

Try in order:
1. **`codex exec --json`** (default, when local codex CLI is available)
2. **`codex_broker`** (only when `CODEX_COMPANION_APP_SERVER_ENDPOINT` is set or `broker.json` exists for the exact cwd; fail/busy → degrade immediately, no retry)
3. **File mailbox (manual)** (when spawn is blocked or above options fail)
4. **User relay** (last resort)

Write `-o` files to `%TEMP%`/`$TMPDIR` only. Stdout JSONL is the primary parse target.
Append sandbox flags based on `FRIEND_TRUST_LEVEL` (see Trust Level section).

### Round 1 command (Claude → Codex)

Check `.bridge.pending` / `.bridge_state.json` `pending_for_claude` and failure cache first. If clear and codex CLI is available:

> Windows PowerShell details, `session_id`/`thread_id` extraction, tee archiving: see `C:\Users\83233\.claude\skills\friend\POWERSHELL_TIPS.md`

```bash
codex exec --skip-git-repo-check -C "<task_dir>" --json --sandbox workspace-write \
  -o "<TMP>/friend_reply_round<N>.txt" \
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

Key flags: `--skip-git-repo-check` (not limited to git repos), `-C` (sets cwd for Codex file access), `--json` (JSONL event stream with a resume id: `thread_id` on newer Codex CLI, `session_id` on older CLI), `--sandbox workspace-write` (default trust level; use `--sandbox read-only` for safe mode), `-o` (writes final reply to file), `- <<'EOF'` (stdin heredoc). Recommended timeout: 7200000. On error or timeout: retry once with corrected params. Do not loop-retry auth errors — degrade to manual or escalate to user.

Read reply: `Read <TMP>/friend_reply_round<N>.txt`

### Multi-round

Extract the resume id from `--json` stdout (`thread_id` on newer Codex CLI, `session_id` on older CLI; event `session_configured` or similar), then:

```bash
codex exec resume <thread_id-or-session_id> --skip-git-repo-check --json --sandbox workspace-write \
  -o "<TMP>/friend_reply_round<N>.txt" \
  - <<'EOF'
[FRIEND_CONSULT round=2]
Revised based on your feedback: <revised plan>
Unchanged (with reason): <kept points + rationale>
Please re-evaluate: AGREE / REFINE / OBJECT
EOF
```

`codex exec resume` does **not** accept `-C`. If the resume id fails, use `--last` or start a new session with the previous round's key points.

- **REFINE** → incorporate and continue
- **OBJECT** → same, include your rationale
- **Max 5 rounds.** Still diverging → escalate to user:

```
Peer consultation: 5 rounds without consensus.
My plan: <key points>
Codex's plan: <key points>
Core disagreement: <what differs>
Please decide.
```

### Reaching consensus (AGREE)

Prefix reply with: "Agreed with Codex:" then proceed.

### After consensus: choose the smallest work route

After `AGREE`, choose the lowest-coupling route that satisfies the consensus. Do not duplicate `helper` or `handoff` protocols here.

- **Self-execute**: Claude does the work. Use `朋友` again for final review when risk, complexity, or the consensus calls for peer review.
- **Counterpart-execute**: Codex should do the work while Claude reviews. Use the existing write-scope mechanism: `Please directly modify: <path(s)>`. Include owned paths/tasks, validation, and return expectations.
- **Helper route**: work is parallelizable, has multiple owners, or needs external CLI helpers. The `朋友` consensus should state goal, owners, integrator/review-by, validation, and open risks; then invoke `helper`/`帮手`. `helper` owns launch/return briefs and the final review packet.

If the route is unclear, ask the user or state a minimal assumption. If the route ends at a session boundary or role switch, also see "Suggest handoff" above. During an anti-recursion response, only return `AGREE` / `REFINE` / `OBJECT`; the originating session chooses the route.

## Anti-recursion (critical)

When you receive input where **the first non-blank line** is `[FRIEND_CONSULT round=N]`:
- Reply AGREE / REFINE / OBJECT
- **Allowed**: `codex exec resume <thread_id-or-session_id>` to deliver this verdict back to the originating session
- **Prohibited**: starting a reverse `[FRIEND_CONSULT]`; expanding scope in a resume prompt; asking the counterpart to invoke third-party tools
- Nesting boundary = "does this create a new reverse consultation chain?" (not "does this call the counterpart's CLI?")
- You may read files / run read-only commands to verify facts

## Manual Fallback: File Mailbox

When `codex exec` is unavailable, or the user says "read `C:\Users\83233\.shared\friend\codex_to_claude.md`":

1. Read `C:\Users\83233\.shared\friend\codex_to_claude.md` (or `scripts/friend_mailbox_claude.py read`)
2. If first non-blank line is `[FRIEND_CONSULT round=N]`, reply per anti-recursion rules, write to `C:\Users\83233\.shared\friend\claude_to_codex.md` (or `scripts/friend_mailbox_claude.py write --reply-file <file>`)
3. Tell user: "Reply written to `C:\Users\83233\.shared\friend\claude_to_codex.md`. Codex's watcher will pick it up; if not running, please relay to Codex."

Multi-round: overwrite the same two files each time.

**Single-instance constraint**: one bridge `--watch` process per mailbox max; clean stale lock before starting (`.bridge_watch.lock` heartbeat, stale threshold: max(3×poll, 30s)).

**Transport layers**: bridge defaults to `--transport manual` (stdlib only, no external deps) — protocol guard + archive + `pending_for_*` state + `.bridge.pending` sentinel; **no `claude -p`**. Use `--transport claude_cli` for auto-dispatch; failures use `failure_cache` circuit-break (TTL 5–15 min by error class, env `FRIEND_BRIDGE_FAILURE_TTL_SECONDS`; backoff cap 1h). `--probe` in manual mode shows status only; `--probe --transport claude_cli` actually tests claude.

**Pending check (mandatory)**: before starting any consultation or when the user prompts, check `.bridge.pending` or `pending_for_claude` in `.bridge_state.json`; if true, process `codex_to_claude.md` first.

**Shallow watcher**: `scripts/surface_friend_pending.sh` copies pending inbox to `C:\Users\83233\.shared\friend\CLAUDE_PENDING_INBOX.md` without auto-replying.

**Queue (preferred for manual new requests)**: read `C:\Users\83233\.shared\friend\queue\to_claude\<id>.md` via `scripts/friend_mailbox_claude.py queue next`; reply with `queue reply <id> --reply-file <file>`. Old mailbox files remain for compatibility. See `C:\Users\83233\.shared\friend\FRIEND_QUEUE_HANDOFF.md`.

## Trust Level and Permissions

### FRIEND_TRUST_LEVEL (symmetric both directions)

| Level | Claude → Codex (`codex exec`) | Codex → Claude (`claude -p` via bridge) |
|---|---|---|
| **safe** | `--sandbox read-only` | `--allowedTools Read,Grep,Glob,LS` |
| **workspace** (default) | `--sandbox workspace-write` | `--permission-mode acceptEdits --allowedTools Read,Grep,Glob,LS,Edit,MultiEdit,Write` |
| **danger** | `--dangerously-bypass-approvals-and-sandbox` | `--dangerously-skip-permissions` |

`danger` requires both `FRIEND_TRUST_LEVEL=danger` **and** `FRIEND_TRUST_DANGER_ACK=I_UNDERSTAND`; otherwise bridge silently downgrades to `workspace`.

Append the corresponding flag to `codex exec`. If `FRIEND_CODEX_EXEC_EXTRA_FLAGS` is set, `shlex.split` and append (set `FRIEND_ALLOW_TRUST_OVERRIDE=1` to bypass conflict detection).

### FRIEND_DISPATCH_MODE (bridge `claude -p` direction only)

| Mode | Behavior |
|---|---|
| **manual** | No auto `claude -p` dispatch; protocol guard + archive only |
| **auto** (default) | Existing `failure_cache` + TTL behavior |
| **eager** | Non-auth failures: TTL × 0.5 (floor 30s); auth unchanged; `--force` is the only bypass |

Priority: CLI arg > env var > default. Legacy numeric values (`0/1/2`) map to `manual/auto/eager` with a deprecation warning; permission level always defaults to `workspace`.

Config via env var or CLI arg only; see `C:\Users\83233\.shared\friend\trust-profile.env.example`.

## Protocol Vocabulary

- **AGREE**: accept current plan, proceed to execution
- **REFINE**: direction is right, needs specific changes
- **OBJECT**: plan is fundamentally wrong — provide alternative

Do not invent new terms. When information is missing: `REFINE: need to confirm X/Y/Z with the user first`.

When citing paths, function names, commands, or tool results, include the source (which file, which command). If unverified, say so.

## Do Not Trigger

- Pure Q&A (explain code, look up docs) → answer independently
- Owner says "don't loop in Codex" or "let me check this myself"
- Receiving a reverse `[FRIEND_CONSULT]` → see anti-recursion
- Already processing a Codex reply within an active consultation

## Sync Notification

For unilateral notification of changes affecting the counterpart's future behavior (skill, hook, global rules, memory). Not multi-round.

- First non-blank line: `[NOTIFY]`. Body must include: source, category, changed file paths, diff summary, impact, expected action, sanitized summary. **Any long-term rule change must send `[NOTIFY]`.**
- Before writing a `[NOTIFY]` to Codex's inbox, check `pending_for_codex` in `.bridge_state.json`; if true, wait for it to be processed or use the queue.
- Notify only for changes affecting judgment or capability. Not for project code, logs, cache, secrets, or tokens.
- On receiving `[NOTIFY]`: reply `ACK: received — <key points>`; evaluate and adapt locally if applicable. Do not blindly mirror.
- If notification reveals a real disagreement, open a `[FRIEND_CONSULT]`.

### Optional: cross-clone canonical pointer

If `C:\Users\83233\.shared\friend\CURRENT.md` exists, read its `canonical` path before consulting. Verify repo/branch/head/dirty state with live commands — do not treat CURRENT as a fact source.

CURRENT may only contain `updated`, `canonical`, `owner`, `expires`. Before writing: if `owner != claude` and not yet expired, do not overwrite — send `[NOTIFY] request-handoff` instead. If `owner == claude` or expired: atomic temp-file + rename. Default `expires = updated + 30min`; renew both `updated` and `expires` in long sessions.
