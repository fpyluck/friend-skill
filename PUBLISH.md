# Publishing this release to GitHub

> **TL;DR**: Don't `git push --force` a new root. Clone the existing repo, overlay this release tree, commit, push. Old history preserved.

This file documents how to publish the contents of this directory to
`https://github.com/fpyluck/friend-skill` while preserving prior commit history.

## Why not just `git init` + force push?

The local `friend-skill/` directory was rebuilt from scratch (the old working copy
was deleted). `git init` here would create a new root commit with no parent,
unrelated to the existing GitHub history. Pushing it would overwrite all prior
commits on `origin/main`, losing the project's chronological record.

## Recommended publish workflow

Run the following on a machine with working network access to GitHub
(this environment failed `git clone` with `Connection reset` / `Failed to connect`).

```bash
# 1. Pick a workspace separate from this release tree
cd /some/scratch/dir

# 2. Clone the canonical repo (preserves history)
git clone https://github.com/fpyluck/friend-skill.git
cd friend-skill

# 3. Overlay this release tree on top of the cloned working copy
#    (assume RELEASE_DIR points at this directory)
RELEASE_DIR=/path/to/friend-skill-release-tree

# Mirror file contents (do not delete .git, .github, etc.)
rsync -av --delete \
  --exclude='.git/' \
  --exclude='.github/' \
  "$RELEASE_DIR"/ ./

# 4. Inspect changes
git status
git diff --stat HEAD
git diff HEAD                  # spot-check critical files

# 5. Stage and commit (write a meaningful release message)
git add -A
git commit -m "release: transport-layered v2 (manual default + claude_cli opt-in + failure cache + watch singleton)

- bridge.py: --transport {manual,claude_cli}; manual default no longer calls claude -p
- bridge.py: --probe / --wait-reply / failure cache with classification + exponential backoff
- bridge.py: WatchLock with token + heartbeat (best-effort singleton)
- bridge.py: pending_for_{claude,codex} state + sentinel .bridge.pending
- claude/scripts/friend_mailbox_claude.py: ClaudeCode-side helper (status/read/watch/write)
- SKILL.md (both sides): governance baseline ([NOTIFY] required fields), anti-recursion
  redefined as 'no new reverse [FRIEND_CONSULT] chain', mailbox pending checks
- AGENTS.md.snippet: managed-block markers for idempotent install
- install.sh / install.ps1: cross-platform; managed-block AGENTS.md update
- README.md: rewritten; English summary"

# 6. Push (you may want to dry-run first)
git push --dry-run origin main
git push origin main
```

## Caveats

### `wait_reply` deferred state update

If `friend_mailbox_bridge.py --wait-reply` cannot acquire `.bridge.lock` before
its deadline (e.g. a long-running `--watch` tick is mutating state), it will
still print the Claude reply to stdout (so the caller doesn't lose the
message), then exit. The `last_consumed_outbox_sha256` is **not** persisted in
that edge case. Re-running `--wait-reply` may therefore print the same reply
once more until it successfully writes state. This is acceptable behavior
(the safer of the two failure modes).

### Bridge runs unattended; default `manual` is intentional

End-to-end automatic round-trip in **manual** transport requires:

- A `friend_mailbox_bridge.py --watch --transport manual` process running on
  one side (any side; the file mailbox is shared).
- ClaudeCode to use `friend_mailbox_claude.py watch --print-inbox` then
  `friend_mailbox_claude.py write --reply-file <path>` after it produces a
  reply.

The bridge will **not** call Claude/Codex APIs, will **not** mutate global
shell / proxy / PATH / settings, and will **not** auto-generate replies.

### `claude_cli` transport opt-in

Set `--transport claude_cli` on the bridge for auto-dispatch via `claude -p`.
This requires `claude -p --output-format json` to actually return valid JSON
in the local environment. Diagnose with:

```bash
python3 ~/.shared/friend/friend_mailbox_bridge.py --probe --transport claude_cli
```

Output `failed:proxy` indicates the local Claude API gateway intercepts
requests; the bridge then writes a `failure_cache` and skips dispatch within
TTL (`5–15 min` by classification, configurable via
`FRIEND_BRIDGE_FAILURE_TTL_SECONDS`).
