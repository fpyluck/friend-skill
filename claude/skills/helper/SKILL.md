---
name: helper
description: 'Helper skill - Claude x Codex split execution after 朋友 consensus. Triggers when user writes "帮手", "/helper", or "helper" as a standalone message or invocation, or asks to 分工, divide the work, or split with Claude/Codex. Use for large, parallelizable work after Friend/朋友 agrees to divide the task, including optional external CLI helpers. Coordinates file-disjoint ownership, helper tasks, completion notes, integration, and final 朋友 mutual review; do not use for simple tasks or before 朋友 consensus.'
---

# Helper (帮手) - Claude x Codex Split Execution

Use this skill when Claude and Codex should both implement part of a large task. Helper does not replace `朋友`; it starts only after `朋友` reaches consensus, and it ends by invoking `朋友` for mutual review.

## Prerequisite

Before splitting work, confirm a current `朋友` consensus covers:

- Shared goal and why parallel work is worthwhile
- Disjoint ownership boundaries
- Integrator and final reviewer
- Validation commands or explicit `N/A`

If any item is missing, invoke `朋友` first. If the task is small, skip Helper.

## Work Card

Send the work card through the existing `朋友` transport. Do not repeat mailbox, CLI, or bridge mechanics here.

```text
[HELPER_WORK_CARD]
goal: <one sentence from the 朋友 consensus>
mode: file-disjoint
codex: <owned paths/modules/tasks>
claude: <owned paths/modules/tasks>
integrator: <Claude | Codex>
validate: <commands both sides must run, or N/A>
review-by: <Claude | Codex; defaults to integrator>
stop-if: <overlap needed, validation changes, or shared config/global behavior is touched>
helpers: <optional external CLI helpers; see below, or N/A>
```

Default to file-disjoint ownership. If either side needs a path or task owned by the other side, stop and renegotiate the split instead of editing across the boundary.

Before sending the work card, run the read-only gate:
`python C:\Users\83233\.shared\friend\friend_gate.py --mailbox C:\Users\83233\.shared\friend check-work-card <work-card-file>`
Overlapping ownership paths are a hard stop; missing fields are warnings to resolve before launch.

## During Work

- Work only inside your assigned ownership.
- Do not revert, reformat, or silently adjust the other side's files.
- Keep shared updates compact and factual.
- While Helper is active, do not start independent `朋友` consultations for slice-level choices. Use the agreed `review-by` final review, unless a blocker requires renegotiating the split.

## External Helpers

Claude and Codex are the co-leads. Other installed CLIs may be invited as leaf helpers, but never as final authorities. Use them for bounded research, review, generation, or file-disjoint implementation, then inspect their output before integration.

Add helpers to the work card like this:

```text
helpers:
  - name: <cli or role>
    command: <probe or invocation, or unknown>
    trust: known | probe | skip
    mode: read-only | write
    owned-paths: <paths/tasks, or N/A>
    output-format: plain-text-summary | diff-only | json | any
    timeout: <limit, or N/A>
    brief: include | minimal | none  # default include for new CLI helpers
    playbook: create | refresh  # optional; omit when not needed
```

Discovery is two-stage: first use local, low-side-effect probes such as `command -v <cli>` and `<cli> --help`; then decide `known`, `probe`, or `skip`. Unknown or interactive-only CLIs start as `probe` and read-only. Skip helpers that cannot be bounded without user input.

For examples and registry ideas, read `references/external-cli-helpers.md` only when external helpers are actually being considered. For stored invocation recipes, check `references/external-cli-playbooks.md` before probing; create or refresh a playbook after a successful new invocation or a changed workflow.

Playbooks are hints, not authority. If a playbook fails, re-discover from local help and current docs when useful, update the entry if the new approach works, and ask the user for the specific missing detail if it still fails. Never store secrets; recording environment variable names is fine.

Use a launch brief when starting a new CLI helper. It is handoff-shaped but task-local: enough context to work, not a persistent project diary.

Before launching a substantial external helper, check its playbook, docs, or help output for a native handoff, handover, or resume feature. If one exists, request it and record `handoff-mode: native`; `[HELPER_EXTERNAL_RESULT]` is still required in either mode - `native` flags the native artifact as the primary record, `helper-contract` means `[HELPER_EXTERNAL_RESULT]` is the sole record. If the return brief is missing or empty, treat as `status: blocked` and do not count the helper complete.

```text
[HELPER_LAUNCH_BRIEF]
project-root: <absolute path>
environment: <shell/OS/runtime notes, or N/A>
already-done: <what Claude/Codex/other helpers have completed or ruled out>
friend-consensus: <the 朋友-agreed plan and division relevant to this helper>
owned-scope: <this helper's exact slice>
relevant-files: <important paths and why they matter>
validation: <commands or checks expected, or N/A>
constraints: <non-secrets, boundaries, user preferences, or N/A>
return-contract: <expected [HELPER_EXTERNAL_RESULT] style and format>
```

External helper prompt:

```text
[HELPER_EXTERNAL_TASK]
goal: <bounded task>
cwd: <absolute path>
launch-brief: <embed [HELPER_LAUNCH_BRIEF] unless brief is minimal or none>
owned-paths: <paths/tasks>
allowed-actions: <read-only or exact write scope>
forbidden-actions: invoke 朋友, invoke helper/帮手, call parent agent, touch secrets
output-format: <required format>
return: [HELPER_EXTERNAL_RESULT]
```

External helper result:

```text
[HELPER_EXTERNAL_RESULT]
helper: <name>
status: done | blocked | skipped
handoff-mode: native | helper-contract
format-used: <actual format>
truncated: yes | no
scope-completed: <what was actually finished, not just attempted>
changed-paths: <paths changed, or N/A>
validation: <command + result, or N/A>
summary: <brief result>
review-notes: <what Claude/Codex should inspect first, or N/A>
next-actions: <suggested follow-up, or N/A>
risks: <open risks, or N/A>
```

Fill every result field so the reviewer can proceed even if the helper is gone.

## Completion Note

When your slice is ready or blocked, send:

```text
[HELPER_COMPLETE]
agent: Claude
status: done | blocked
changed-paths: <paths changed, or N/A>
validation: <command + result, or N/A>
needs-from-other: <anything required before integration, or N/A>
notes: <brief risk or handoff note, or N/A>
```

If either status is `blocked`, pause integration and renegotiate the split.

## Final Review

The `review-by` agent collects Claude, Codex, and external helper return briefs, checks the work card boundaries, inspects helper diffs before trusting them, runs validation when feasible, then opens a final `朋友` review with the work card, changed paths, validation results, and open risks. Only claim the combined task is done after that review reaches `AGREE` or the user decides.
