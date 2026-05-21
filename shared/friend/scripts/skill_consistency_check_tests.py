"""
pytest unit tests for skill_consistency_check.py
Run: python -m pytest skill_consistency_check_tests.py -v
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Import module under test
sys.path.insert(0, str(Path(__file__).parent))
import skill_consistency_check as scc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill(tmp_path: Path, name: str, content: str,
                encoding: str = "utf-8") -> Path:
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    p = skill_dir / "SKILL.md"
    p.write_bytes(content.encode(encoding) if isinstance(content, str) else content)
    return tmp_path


def _run(skills_dir: Path, side: str = "claude") -> scc.CheckResult:
    import argparse
    args = argparse.Namespace(side=side, skills_dir=str(skills_dir), strict=False,
                              json_output=False)
    return scc.run_checks(args)


def _findings(result: scc.CheckResult, check: str) -> list[scc.Finding]:
    return [f for f in result.findings if f.check == check]


# ---------------------------------------------------------------------------
# UTF-8 encoding
# ---------------------------------------------------------------------------

def test_utf8_valid(tmp_path):
    _make_skill(tmp_path, "friend", "# Friend\nsome content\n")
    r = _run(tmp_path)
    assert any(f.level == "PASS" and f.check == "utf8_encoding" for f in r.findings)


def test_utf8_invalid(tmp_path):
    skill_dir = tmp_path / "friend"
    skill_dir.mkdir()
    p = skill_dir / "SKILL.md"
    p.write_bytes(b"# Friend\n\xff\xfe invalid bytes\n")
    r = _run(tmp_path)
    fails = [f for f in r.findings if f.check == "utf8_encoding" and f.level == "FAIL"]
    assert fails, "Should FAIL on invalid UTF-8"


# ---------------------------------------------------------------------------
# Mojibake detection
# ---------------------------------------------------------------------------

def test_mojibake_replacement_char(tmp_path):
    content = "# Friend\ntrigger: ���\n"
    _make_skill(tmp_path, "friend", content)
    r = _run(tmp_path)
    fails = [f for f in r.findings if f.check == "mojibake" and f.level == "FAIL"]
    assert fails, "Should FAIL on replacement chars"


def test_mojibake_powershell_literal(tmp_path):
    # 鏈嬪弸 is 朋友 garbled through GBK
    content = "# Friend\ntrigger: 鏈嬪弸\n"
    _make_skill(tmp_path, "friend", content)
    r = _run(tmp_path)
    fails = [f for f in r.findings if f.check == "mojibake" and f.level == "FAIL"]
    assert fails, "Should FAIL on PowerShell garbled literal"


def test_mojibake_clean(tmp_path):
    _make_skill(tmp_path, "friend", "# Friend\n朋友 帮手\n")
    r = _run(tmp_path)
    passes = [f for f in r.findings if f.check == "mojibake" and f.level == "PASS"]
    assert passes, "Clean Chinese should PASS"


# ---------------------------------------------------------------------------
# Hard path detection
# ---------------------------------------------------------------------------

def test_hard_path_warn_prose(tmp_path):
    content = "# Friend\nPlease read C:\\Users\\alice\\notes.md for details.\n"
    _make_skill(tmp_path, "friend", content)
    r = _run(tmp_path)
    warns = [f for f in r.findings if f.check == "hard_path" and f.level == "WARN"]
    assert warns, "Should WARN on hard user path in prose"


def test_hard_path_ok_in_code_block(tmp_path):
    content = "# Friend\n```\nworkdir: /home/user/project\n```\n"
    _make_skill(tmp_path, "friend", content)
    r = _run(tmp_path)
    fails = [f for f in r.findings if f.check == "hard_path" and f.level == "FAIL"]
    assert not fails, "Hard path inside code block should not FAIL"
    warns = [f for f in r.findings if f.check == "hard_path" and f.level == "WARN"]
    assert not warns, "Hard path inside code block should not WARN"


# ---------------------------------------------------------------------------
# Required sections
# ---------------------------------------------------------------------------

def test_required_sections_pass(tmp_path):
    content = (
        "# Friend\n"
        "## Consultation Protocol\n...\n"
        "## Anti-recursion\n...\n"
        "## Trust Level\n...\n"
    )
    _make_skill(tmp_path, "friend", content)
    r = _run(tmp_path)
    passes = [f for f in r.findings if f.check == "required_sections" and f.level == "PASS"]
    assert passes


def test_required_sections_fail(tmp_path):
    content = "# Friend\n## Consultation Protocol\n...\n"
    _make_skill(tmp_path, "friend", content)
    r = _run(tmp_path)
    fails = [f for f in r.findings if f.check == "required_sections" and f.level == "FAIL"]
    assert fails, "Missing required sections should FAIL"
    assert "Anti-recursion" in fails[0].message or "Trust Level" in fails[0].message


# ---------------------------------------------------------------------------
# Env var priority
# ---------------------------------------------------------------------------

def test_env_var_priority_fail(tmp_path):
    # Uses XIONGDIMEN_SHARED_ENV without BUDDYS_SHARED_ENV
    content = "# Handoff\nread ${XIONGDIMEN_SHARED_ENV:-default}\n"
    _make_skill(tmp_path, "handoff", content)
    r = _run(tmp_path)
    fails = [f for f in r.findings if f.check == "env_var_priority" and f.level == "FAIL"]
    assert fails, "Should FAIL when XIONGDIMEN_* has no BUDDYS_* counterpart"


def test_env_var_priority_pass(tmp_path):
    content = "# Handoff\nread ${BUDDYS_SHARED_ENV:-${XIONGDIMEN_SHARED_ENV:-default}}\n"
    _make_skill(tmp_path, "handoff", content)
    r = _run(tmp_path)
    fails = [f for f in r.findings if f.check == "env_var_priority" and f.level == "FAIL"]
    assert not fails, "BUDDYS_* wrapping XIONGDIMEN_* should PASS"


# ---------------------------------------------------------------------------
# Legacy output marker
# ---------------------------------------------------------------------------

def test_legacy_output_fail(tmp_path):
    content = "# Buddys\nAdd [XIONGDIMEN_BRIEF] to the output.\n"
    _make_skill(tmp_path, "xiongdimen", content)
    r = _run(tmp_path)
    fails = [f for f in r.findings if f.check == "legacy_output" and f.level == "FAIL"]
    assert fails, "Legacy marker in output verb context should FAIL"


def test_legacy_output_ok_in_accept_context(tmp_path):
    content = (
        "# Buddys\n"
        "Accept legacy [XIONGDIMEN_BRIEF] and [XIONGDIMEN_GEMINI_QUERY] as the same.\n"
    )
    _make_skill(tmp_path, "xiongdimen", content)
    r = _run(tmp_path)
    fails = [f for f in r.findings if f.check == "legacy_output" and f.level == "FAIL"]
    assert not fails, "Legacy marker in accept-legacy context should not FAIL"


# ---------------------------------------------------------------------------
# Shell mismatch
# ---------------------------------------------------------------------------

def test_shell_mismatch_warn_claude_side(tmp_path):
    content = (
        "# Friend\n"
        "```bash\n"
        "codex exec - << 'EOF'\nhello\nEOF\n"
        "```\n"
    )
    _make_skill(tmp_path, "friend", content)
    r = _run(tmp_path, side="claude")
    warns = [f for f in r.findings if f.check == "shell_mismatch" and f.level == "WARN"]
    assert warns, "bash heredoc without PowerShell note should WARN on claude side"


def test_shell_mismatch_pass_with_ps_note(tmp_path):
    content = (
        "# Friend\n"
        "```bash\n"
        "cat <<'EOF' | command\nhello\nEOF\n"
        "```\n"
        "See POWERSHELL_TIPS.md for Windows equivalent.\n"
    )
    _make_skill(tmp_path, "friend", content)
    r = _run(tmp_path, side="claude")
    warns = [f for f in r.findings if f.check == "shell_mismatch" and f.level == "WARN"]
    assert not warns, "PS note present should not WARN"


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def test_json_output_structure(tmp_path, capsys):
    _make_skill(tmp_path, "friend", "# Friend\n## Consultation Protocol\n## Anti-recursion\n## Trust Level\n")
    import argparse
    args = argparse.Namespace(side="claude", skills_dir=str(tmp_path), strict=False,
                              json_output=True)
    r = scc.run_checks(args)
    out = scc._fmt_json(r)
    data = json.loads(out)
    assert "checks" in data
    assert "summary" in data
    assert set(data["summary"].keys()) == {"passed", "warnings", "failures"}


# ---------------------------------------------------------------------------
# Gate reachability (integration — skipped if gate not present)
# ---------------------------------------------------------------------------

def test_gate_reachability_warn_when_missing(tmp_path, monkeypatch):
    # Temporarily make home a temp dir so gate is definitely not found
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    r = scc.CheckResult()
    scc._check_gate_reachability(r)
    warns = [f for f in r.findings if f.check == "gate_reachability" and f.level == "WARN"]
    assert warns, "Missing gate should produce WARN"
