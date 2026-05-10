# External CLI Helpers

Use this reference only when `帮手` is considering helpers beyond Claude and Codex.

## Pattern

Treat every external CLI as a bounded worker:

- `known`: previously used successfully in this environment; may run the agreed invocation.
- `probe`: available but not yet trusted; use read-only analysis or dry-run style prompts.
- `skip`: unavailable, too interactive, too broad, or unsafe without user confirmation.

Prefer manager-owned helpers over full handoffs: Claude and Codex keep the final integration and review responsibility.

## Discovery

Start with local probes:

```bash
command -v <cli>
<cli> --help
<cli> --version
```

If help text implies package installation, account mutation, network write, global config edits, or uncontrolled interactivity, mark it `skip` unless the user explicitly wants it.

## Example Helper Card

```text
helpers:
  - name: gemini
    command: gemini --help
    trust: probe
    mode: read-only
    owned-paths: src/search/
    output-format: plain-text-summary
    timeout: 120s
```

## Integration Rule

External output is evidence, not authority. The integrator must inspect the helper's return brief, changed paths or proposed diffs, run validation when feasible, and carry unresolved risks into the final `朋友` review.
