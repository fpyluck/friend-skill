# External CLI Playbooks

This is a small, mutable memory for external CLI helpers used by `帮手`. Keep entries short and update existing entries instead of adding duplicates.

## How To Use

1. When the user asks to include a specific CLI, check this file first.
2. If no entry exists, discover with local probes and current official docs when needed, then add a playbook after a successful bounded invocation.
3. If an entry fails, refresh it from current help/docs and replace the stale details.
4. If the refreshed approach still fails, ask the user for the specific missing detail, such as auth, install path, or interactive choice.

Playbooks are reusable hints. Claude and Codex still inspect results and use `朋友` for final review.

## Template

```text
### <cli-name>
aliases: [<names users may say>]
last_verified: <YYYY-MM-DD or unknown>
trust: known | probe | skip
env_required: [<ENV_VAR_NAMES_ONLY>]
probe_commands:
  - command -v <cli>
  - <cli> --help
invocation_pattern: <bounded command or prompt shape; no secrets>
task_prompt_shape: <how to pass [HELPER_EXTERNAL_TASK], if applicable>
output_contract: <plain-text-summary | diff-only | json | any>
known_limits: <auth, interactivity, write limitations, or N/A>
refresh_when: <help output changes, command fails, user reports stale behavior, or N/A>
notes: <brief operational memory, or N/A>
```

## Entries

No external CLI playbooks have been recorded yet.
