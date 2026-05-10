from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MAILBOX_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = MAILBOX_ROOT / "friend_gate.py"
BRIDGE = MAILBOX_ROOT / "friend_mailbox_bridge.py"


VALID_CONSULT = """[FRIEND_CONSULT round=1]

Phase: PLAN
Task: test

## Project Context (required for round=1)
- Project root: /tmp/example
- Execution environment: N/A
- Project type: N/A
- Virtual env: N/A
- Activation command: N/A
- Commands:
  - test: N/A
  - build: N/A
  - run: N/A
  - lint: N/A
- Key constraints: N/A
- Key file references: N/A

My draft:
N/A

Review points:
1. Decision: AGREE / REFINE / OBJECT
"""


COMPLETE_HANDOFF = """---
project_key: "example"
title: "Example"
updated_at: "2026-05-10T00:00:00+08:00"
canonical_path: "/tmp/example"
mailbox_root: "/tmp/mailbox"
handoff_path: "/tmp/mailbox/handoffs/example.md"
---

# Example Handoff

## current_objective

- Background: Example background
- Goal: Example goal
- Current stopping point: Ready
- Out of scope: N/A

## environment_commands

- Project root: `/tmp/example`
- Execution environment: WSL bash
- Virtual env/container: N/A
- Run: N/A
- Test: N/A
- Build: N/A
- Lint: N/A
- Last verified: N/A
- Unverified: N/A

## file_map

1. `/tmp/example` - project root

## open_issues

1. N/A

## decisions_and_changes

1. Gate checks added.

## error_ledger

| Error / symptom | Root cause | Fix | Prevention |
|---|---|---|---|
| N/A | N/A | N/A | N/A |

## next_actions

1. Run tests.

## agent_notes

- For Codex: N/A
- For Claude: N/A
- Collaboration notes: N/A
- External refs: N/A

## owner_review

- N/A
"""


VALID_WORK_CARD = """[HELPER_WORK_CARD]
goal: implement separate slices
mode: file-disjoint
codex: /tmp/project/src/codex
claude: /tmp/project/src/claude
integrator: Codex
validate: python -m unittest
review-by: Codex
stop-if: overlap needed
helpers: N/A
"""


class FriendGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.mailbox = Path(self.tmp.name) / "mailbox"
        (self.mailbox / "queue" / "to_claude").mkdir(parents=True)
        (self.mailbox / "queue" / "to_codex").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_gate(self, *args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--mailbox", str(self.mailbox), *args],
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )

    def write(self, name: str, text: str) -> Path:
        path = Path(self.tmp.name) / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_check_consult_valid(self) -> None:
        path = self.write("consult.md", VALID_CONSULT)
        proc = self.run_gate("check-consult", str(path))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_check_consult_invalid_marker_is_hard_fail(self) -> None:
        path = self.write("bad-consult.md", "hello\n")
        proc = self.run_gate("check-consult", str(path))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("ERROR", proc.stdout)

    def test_check_consult_missing_context_warns(self) -> None:
        path = self.write("missing-context.md", "[FRIEND_CONSULT round=1]\n\nTask: test\n")
        proc = self.run_gate("check-consult", str(path))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Project Context", proc.stdout)

    def test_check_consult_secret_is_hard_fail(self) -> None:
        path = self.write("secret-consult.md", VALID_CONSULT + "\ntoken = abcdefghijk\n")
        proc = self.run_gate("check-consult", str(path))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("possible secret", proc.stdout)

    def test_check_handoff_empty_template_warns(self) -> None:
        path = self.write("template.md", COMPLETE_HANDOFF.replace("Example background", "{{background}}"))
        proc = self.run_gate("check-handoff", str(path))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("template placeholders", proc.stdout)

    def test_check_handoff_complete_passes(self) -> None:
        path = self.write("handoff.md", COMPLETE_HANDOFF)
        proc = self.run_gate("check-handoff", str(path))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_check_handoff_secret_is_hard_fail(self) -> None:
        path = self.write("handoff-secret.md", COMPLETE_HANDOFF + "\npassword: abcdefghijk\n")
        proc = self.run_gate("check-handoff", str(path))
        self.assertEqual(proc.returncode, 2)

    def test_check_work_card_overlap_is_hard_fail(self) -> None:
        text = VALID_WORK_CARD.replace("/tmp/project/src/claude", "/tmp/project/src/codex/ui")
        path = self.write("overlap-card.md", text)
        proc = self.run_gate("check-work-card", str(path))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("overlapping ownership paths", proc.stdout)

    def test_check_work_card_disjoint_passes(self) -> None:
        path = self.write("work-card.md", VALID_WORK_CARD)
        proc = self.run_gate("check-work-card", str(path))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_check_work_card_missing_fields_warns(self) -> None:
        path = self.write("missing-card.md", "[HELPER_WORK_CARD]\ngoal: test\n")
        proc = self.run_gate("check-work-card", str(path))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("missing or empty fields", proc.stdout)

    def test_status_reports_pending_without_mutating_state(self) -> None:
        state_path = self.mailbox / ".bridge_state.json"
        original = {"pending_for_claude": True, "last_inbox_marker": "[NOTIFY]"}
        state_path.write_text(json.dumps(original, indent=2), encoding="utf-8")
        before = state_path.read_text(encoding="utf-8")
        proc = self.run_gate("status", "--json")
        after = state_path.read_text(encoding="utf-8")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(before, after)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["pending"]["pending_for_claude"])
        self.assertEqual(payload["recommendation"]["route"], "direct_or_queue")

    def test_manual_bridge_same_tick_keeps_inbox_pending(self) -> None:
        (self.mailbox / "codex_to_claude.md").write_text("[NOTIFY]\nnew inbound\n", encoding="utf-8")
        (self.mailbox / "claude_to_codex.md").write_text("AGREE: old outbound\n", encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable,
                str(BRIDGE),
                "--once",
                "--transport",
                "manual",
                "--mailbox",
                str(self.mailbox),
                "--stable-delay",
                "0",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        state = json.loads((self.mailbox / ".bridge_state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["last_inbox_marker"], "[NOTIFY]")
        self.assertTrue(state["pending_for_claude"])
        self.assertTrue(state["pending_for_codex"])
        self.assertEqual(proc.stdout.strip(), "both_pending")


if __name__ == "__main__":
    unittest.main()
