#!/usr/bin/env python3
"""
skill-consistency-check: validates Claude/Codex skill SKILL.md files for
protocol consistency, encoding correctness, and cross-reference integrity.

Usage:
    python skill_consistency_check.py [--side claude|codex|both]
                                      [--skills-dir DIR]
                                      [--strict]
                                      [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Registry — data-driven, no hardcoded user paths
# ---------------------------------------------------------------------------

REGISTRY: dict = {
    "expected_skills": ["friend", "helper", "handoff", "xiongdimen"],
    "required_sections": {
        "handoff": [
            "current_objective", "next_actions", "environment_commands",
            "file_map", "error_ledger", "decisions_and_changes",
            "open_issues", "agent_notes", "owner_review",
        ],
        "friend": [
            "Consultation Protocol", "Anti-recursion", "Trust Level",
        ],
        "helper": [
            "Routing Boundary", "Input Brief", "Work Card",
            "Execution Rules", "Completion",
        ],
        "xiongdimen": [
            "Activation Boundaries", "Roles", "Flow", "Final Brief",
        ],
    },
    # Markers allowed as active output in skill files
    "allowed_markers": {
        "FRIEND_CONSULT", "FRIEND_BRIEF",
        "HELPER_WORK_CARD", "HELPER_COMPLETE",
        "BUDDYS_BRIEF", "BUDDYS_GEMINI_QUERY",
        "SPLIT: YES",
        "NOTIFY", "ACK",
        "COLLABORATION_REPORT",
        # owner_review tags
        "TODO", "DONE", "USER-ACTION", "SUPPLEMENT",
    },
    # These may appear only in accept/compat contexts, not as new output examples
    "legacy_accept_only": {
        "XIONGDIMEN_BRIEF", "XIONGDIMEN_GEMINI_QUERY", "XIONGDIMEN_FRONTEND_QUERY",
    },
    # (preferred_var, legacy_var) — preferred must appear first or wrap legacy
    "paired_env_vars": [
        ("BUDDYS_SHARED_ENV",  "XIONGDIMEN_SHARED_ENV"),
        ("BUDDYS_GEMINI",      "XIONGDIMEN_GEMINI"),
        ("BUDDYS_PYTHON",      "XIONGDIMEN_PYTHON"),
    ],
    # Required runtime files; use env-var or home-relative notation (no hardcoded user)
    "required_external_files": [
        "%USERPROFILE%\\.shared\\friend\\friend_gate.py",
        "~/.shared/friend/friend_gate.py",
    ],
    # Regex patterns that indicate hard-coded user paths (WARN)
    "hard_path_res": [
        re.compile(r"[A-Za-z]:\\[Uu]sers\\[^\\%\{\s]{2,}\\"),
        re.compile(r"/home/[a-zA-Z0-9_.\-]{2,}/"),
    ],
    # Replacement-character or classic mojibake sequences.
    # Literal garbled strings from PowerShell CP936/GBK mis-read of UTF-8:
    #   朋友→鏈嬪弸  帮手→甯墜  交班→浜ょ彮  兄弟们→鍏勫紵浠  减法→鍑忔硶
    "mojibake_literals": [
        "鏈嬪弸", "甯墜", "浜ょ彮", "鍏勫紵", "鍑忔硶",
        "點點", "脇",            # common garbled punctuation
    ],
    "mojibake_re": re.compile(r"[�]+|[\xc3\xa3\xc2][\x80-\xbf]{2,}"),
    "chinese_trigger_words": ["朋友", "帮手", "交班", "兄弟们", "减法"],
    # Verbs that indicate an output/emit context for legacy markers
    "output_verbs_re": re.compile(
        r"\b(emit|output|produce|send|write|return|add|use)\b", re.IGNORECASE
    ),
}

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    level:   str            # PASS | WARN | FAIL
    check:   str
    file:    str
    line:    Optional[int]
    message: str


@dataclass
class CheckResult:
    findings: list[Finding] = field(default_factory=list)

    def add(self, level: str, check: str, file: str,
            message: str, line: Optional[int] = None) -> None:
        self.findings.append(Finding(level, check, file, line, message))

    @property
    def highest(self) -> str:
        if any(f.level == "FAIL" for f in self.findings):
            return "FAIL"
        if any(f.level == "WARN" for f in self.findings):
            return "WARN"
        return "PASS"

    def counts(self) -> dict[str, int]:
        return {
            "passed":   sum(1 for f in self.findings if f.level == "PASS"),
            "warnings": sum(1 for f in self.findings if f.level == "WARN"),
            "failures": sum(1 for f in self.findings if f.level == "FAIL"),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _expand(path_str: str) -> Path:
    """Expand env-vars and ~ without any hardcoded user component."""
    return Path(os.path.expandvars(os.path.expanduser(path_str)))


def _skill_roots(side: str, skills_dir: Optional[Path]) -> list[tuple[str, Path]]:
    """Return [(side_label, skills_root), ...] to scan."""
    if skills_dir:
        # Preserve the requested side label so side-specific checks (shell_mismatch etc.) work
        effective_side = side if side != "both" else "claude"
        return [(effective_side, skills_dir)]
    roots: list[tuple[str, Path]] = []
    candidates = {
        "claude": [
            _expand("%USERPROFILE%") / ".claude" / "skills",
            Path.home() / ".claude" / "skills",
        ],
        "codex": [
            _expand("%USERPROFILE%") / ".codex" / "skills",
            Path.home() / ".codex" / "skills",
        ],
    }
    sides = ["claude", "codex"] if side == "both" else [side]
    for s in sides:
        for p in candidates[s]:
            if p.exists():
                roots.append((s, p))
                break
    return roots


def _collect_skills(roots: list[tuple[str, Path]],
                    all_skills: bool = False) -> list[tuple[str, str, Path]]:
    """Yield (side, skill_name, path) for protocol SKILL.md files.

    By default only yields the four known collaborative skills to avoid noise
    from unrelated skill files in the same directory.  Pass all_skills=True
    (via --all-skills) to scan every SKILL.md under the roots.
    """
    target = set(REGISTRY["expected_skills"])
    result = []
    for side, root in roots:
        for p in sorted(root.glob("*/SKILL.md")):
            name = p.parent.name
            if all_skills or name in target:
                result.append((side, name, p))
    return result


def _read_bytes(path: Path) -> Optional[bytes]:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _read_text(path: Path) -> Optional[str]:
    raw = _read_bytes(path)
    if raw is None:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


# ---------------------------------------------------------------------------
# Per-file checks
# ---------------------------------------------------------------------------

def _check_utf8(side: str, name: str, path: Path, result: CheckResult) -> bool:
    raw = _read_bytes(path)
    if raw is None:
        result.add("FAIL", "utf8_encoding", str(path), "cannot read file")
        return False
    try:
        raw.decode("utf-8")
        result.add("PASS", "utf8_encoding", str(path), "valid UTF-8")
        return True
    except UnicodeDecodeError as exc:
        result.add("FAIL", "utf8_encoding", str(path), f"invalid UTF-8 at byte {exc.start}")
        return False


def _check_mojibake(side: str, name: str, path: Path, text: str,
                    result: CheckResult) -> None:
    pat      = REGISTRY["mojibake_re"]
    literals = REGISTRY["mojibake_literals"]
    cw_re    = re.compile("|".join(re.escape(w) for w in REGISTRY["chinese_trigger_words"]))
    for lineno, line in enumerate(text.splitlines(), 1):
        if pat.search(line):
            result.add("FAIL", "mojibake", str(path),
                       f"replacement/mojibake chars: {line[:80]!r}", line=lineno)
            return
        if any(lit in line for lit in literals):
            result.add("FAIL", "mojibake", str(path),
                       f"known PowerShell garbled sequence: {line[:80]!r}", line=lineno)
            return
        if cw_re.search(line) and "�" in line:
            result.add("FAIL", "mojibake", str(path),
                       f"trigger word near replacement char: {line[:80]!r}", line=lineno)
            return
    result.add("PASS", "mojibake", str(path), "no mojibake detected")


def _check_hard_paths(side: str, name: str, path: Path, text: str,
                      result: CheckResult) -> None:
    pats = REGISTRY["hard_path_res"]
    hits: list[tuple[int, str]] = []
    in_code_block = False
    for lineno, line in enumerate(text.splitlines(), 1):
        # Track fenced code blocks — paths inside are treated as illustrative examples
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        for pat in pats:
            if pat.search(line):
                hits.append((lineno, line.strip()[:80]))
                break
    if hits:
        for lineno, snippet in hits[:3]:
            result.add("WARN", "hard_path", str(path),
                       f"hard user path outside code block: {snippet!r}", line=lineno)
    else:
        result.add("PASS", "hard_path", str(path), "no hard user paths detected")


def _check_required_sections(side: str, name: str, path: Path, text: str,
                              result: CheckResult) -> None:
    required = REGISTRY["required_sections"].get(name, [])
    if not required:
        result.add("PASS", "required_sections", str(path),
                   "no required-section spec for this skill — skipped")
        return
    missing = []
    lower_text = text.lower()
    for section in required:
        heading_re = re.compile(
            r"^#{1,4}\s+" + re.escape(section), re.MULTILINE | re.IGNORECASE
        )
        if not heading_re.search(text) and section.lower() not in lower_text:
            missing.append(section)
    if missing:
        result.add("FAIL", "required_sections", str(path),
                   f"missing sections: {missing}")
    else:
        result.add("PASS", "required_sections", str(path), "all required sections present")


def _check_protocol_markers(side: str, name: str, path: Path, text: str,
                             result: CheckResult) -> None:
    # Only enforce the protocol-marker whitelist on the four known collaborative skills
    if name not in REGISTRY["expected_skills"]:
        result.add("PASS", "protocol_markers", str(path),
                   "protocol marker check skipped (non-collab skill)")
        return
    allowed    = REGISTRY["allowed_markers"]
    legacy     = REGISTRY["legacy_accept_only"]
    all_known  = allowed | legacy
    marker_re  = re.compile(r"\[([A-Z][A-Z0-9_: ]+)\]")
    unknown: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in marker_re.finditer(line):
            token = m.group(1).strip()
            # Allow "FRIEND_CONSULT round=N" etc. via prefix match
            if not any(token == a or token.startswith(a + " ") or token.startswith(a + ":")
                       for a in all_known):
                unknown.append((lineno, token))
    if unknown:
        for lineno, token in unknown[:3]:
            result.add("WARN", "protocol_markers", str(path),
                       f"unrecognised marker [{token}]", line=lineno)
    else:
        result.add("PASS", "protocol_markers", str(path), "all markers in whitelist")


def _check_env_var_priority(side: str, name: str, path: Path, text: str,
                             result: CheckResult) -> None:
    issues: list[str] = []
    for preferred, legacy in REGISTRY["paired_env_vars"]:
        # Find ALL occurrences of the legacy var as a standalone token (not as prefix of another var)
        legacy_positions = [m.start() for m in re.finditer(re.escape(legacy) + r'(?![A-Z_])', text)]
        if not legacy_positions:
            continue  # legacy not used at all — fine
        if preferred not in text:
            issues.append(f"{legacy} present but {preferred} missing (add {preferred} as priority)")
            continue
        for lpos in legacy_positions:
            context_start = max(0, lpos - 120)
            context = text[context_start: lpos + len(legacy) + 120]
            if preferred not in context:
                issues.append(
                    f"{legacy} at char {lpos} without {preferred} in surrounding context "
                    f"(possible priority inversion)"
                )
                break  # one report per pair is enough
    if issues:
        for issue in issues:
            result.add("FAIL", "env_var_priority", str(path), issue)
    else:
        result.add("PASS", "env_var_priority", str(path),
                   "env var priority (BUDDYS_* > XIONGDIMEN_*) correct")


def _check_legacy_output(side: str, name: str, path: Path, text: str,
                          result: CheckResult) -> None:
    """Legacy markers must not appear as *output* examples in new content."""
    forbidden = REGISTRY["legacy_accept_only"]
    verb_re   = REGISTRY["output_verbs_re"]
    # Build a byte-offset map so context lookup is line-position-accurate
    line_offsets: list[int] = []
    pos = 0
    for ln in text.splitlines(keepends=True):
        line_offsets.append(pos)
        pos += len(ln)
    for lineno, line in enumerate(text.splitlines(), 1):
        for marker in forbidden:
            if marker in line:
                # Use the actual line start offset, not text.find(line) which can match wrong line
                lstart = line_offsets[lineno - 1]
                ctx_start = max(0, lstart - 200)
                ctx_end   = min(len(text), lstart + len(line) + 200)
                context = text[ctx_start:ctx_end].lower()
                if any(kw in context for kw in ("accept legacy", "compat", "legacy alias",
                                                 "accept", "backward")):
                    continue  # legitimate accept context
                if verb_re.search(line):
                    result.add("FAIL", "legacy_output", str(path),
                               f"legacy marker {marker!r} in output context: {line.strip()[:80]!r}",
                               line=lineno)
                    return
    result.add("PASS", "legacy_output", str(path), "no forbidden legacy output markers")


def _check_cross_references(side: str, name: str, path: Path, text: str,
                              result: CheckResult) -> None:
    r"""Check %USERPROFILE%\... / $HOME/... references for critical runtime files."""
    ref_re = re.compile(
        r"(%USERPROFILE%[\\/][^\s`'\"<>]{4,}|"
        r"\$(?:HOME|USERPROFILE)/[^\s`'\"<>]{4,}|\$\{[A-Z_]+\}/[^\s`'\"<>]{4,})"
    )
    key_names = ("skill.md", "friend_gate", "bridge", "handoff-template",
                 "skill_consistency")
    broken: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in ref_re.finditer(line):
            ref = m.group(1)
            if not any(k in ref.lower() for k in key_names):
                continue
            try:
                expanded = _expand(ref)
                if not expanded.exists():
                    broken.append((lineno, ref))
            except Exception:
                pass
    if broken:
        for lineno, ref in broken[:3]:
            result.add("WARN", "cross_references", str(path),
                       f"possibly broken reference: {ref!r}", line=lineno)
    else:
        result.add("PASS", "cross_references", str(path),
                   "spot-checked cross-references look intact")


def _check_shell_mismatch(side: str, name: str, path: Path, text: str,
                           result: CheckResult) -> None:
    if side == "claude":
        has_heredoc = bool(re.search(r"<<\s*['\"]?EOF", text))
        has_ps_note = bool(re.search(r"PowerShell|POWERSHELL_TIPS|pwsh", text, re.IGNORECASE))
        if has_heredoc and not has_ps_note:
            result.add("WARN", "shell_mismatch", str(path),
                       "bash heredoc present with no PowerShell alternative/note")
        else:
            result.add("PASS", "shell_mismatch", str(path), "shell syntax coverage OK")
    elif side == "codex":
        has_python3_cmd = bool(re.search(r"\bpython3\b", text))
        has_windows_ctx = bool(re.search(r"\bWindows\b|\.cmd\b|PowerShell", text))
        has_fallback    = bool(re.search(r"\bpython\b(?!3)", text))
        if has_python3_cmd and has_windows_ctx and not has_fallback:
            result.add("WARN", "shell_mismatch", str(path),
                       "python3 used in Windows context without python/cmd fallback")
        else:
            result.add("PASS", "shell_mismatch", str(path), "shell syntax coverage OK")
    else:
        result.add("PASS", "shell_mismatch", str(path), "shell check skipped for 'custom' side")


# ---------------------------------------------------------------------------
# Global checks (not per-file)
# ---------------------------------------------------------------------------

def _check_gate_reachability(result: CheckResult) -> None:
    candidates = [
        _expand("%USERPROFILE%") / ".shared" / "friend" / "friend_gate.py",
        Path.home() / ".shared" / "friend" / "friend_gate.py",
    ]
    for p in candidates:
        if p.exists():
            result.add("PASS", "gate_reachability", str(p), "friend_gate.py found")
            return
    result.add("WARN", "gate_reachability", "N/A",
               "friend_gate.py not found — gate preflight unavailable")


def _check_symmetry(
    claude_skills: dict[str, tuple[str, str]],
    codex_skills:  dict[str, tuple[str, str]],
    result: CheckResult,
) -> None:
    """Warn when the same skill exists on both sides but one is missing a required section."""
    common = set(claude_skills) & set(codex_skills)
    if not common:
        return
    for skill_name in sorted(common):
        c_path, c_text = claude_skills[skill_name]
        x_path, x_text = codex_skills[skill_name]
        for section in REGISTRY["required_sections"].get(skill_name, []):
            c_has = section.lower() in c_text.lower()
            x_has = section.lower() in x_text.lower()
            if c_has and not x_has:
                result.add("WARN", "symmetry", x_path,
                           f"section '{section}' present in claude/{skill_name} but missing here")
            elif x_has and not c_has:
                result.add("WARN", "symmetry", c_path,
                           f"section '{section}' present in codex/{skill_name} but missing here")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_checks(args: argparse.Namespace) -> CheckResult:
    result = CheckResult()
    skills_dir_arg = Path(args.skills_dir) if getattr(args, "skills_dir", None) else None
    roots = _skill_roots(args.side, skills_dir_arg)

    if not roots:
        result.add("WARN", "discovery", "N/A",
                   f"no skills directory found for side={args.side!r}")
        return result

    claude_skills: dict[str, tuple[str, str]] = {}
    codex_skills:  dict[str, tuple[str, str]] = {}

    all_skills_flag = getattr(args, "all_skills", False)
    for side, name, path in _collect_skills(roots, all_skills=all_skills_flag):
        if not _check_utf8(side, name, path, result):
            continue
        text = _read_text(path)
        if text is None:
            result.add("FAIL", "read_file", str(path), "UTF-8 decode failed after check")
            continue

        _check_mojibake(side, name, path, text, result)
        _check_hard_paths(side, name, path, text, result)
        _check_required_sections(side, name, path, text, result)
        _check_protocol_markers(side, name, path, text, result)
        _check_env_var_priority(side, name, path, text, result)
        _check_legacy_output(side, name, path, text, result)
        _check_cross_references(side, name, path, text, result)
        _check_shell_mismatch(side, name, path, text, result)

        if side == "claude":
            claude_skills[name] = (str(path), text)
        elif side == "codex":
            codex_skills[name] = (str(path), text)

    _check_gate_reachability(result)
    _check_symmetry(claude_skills, codex_skills, result)

    return result


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _fmt_text(result: CheckResult) -> str:
    lines = []
    for f in result.findings:
        loc = f"{f.file}:{f.line}" if f.line else f.file
        lines.append(f"[{f.level:<4}] {f.check:<22} {loc}: {f.message}")
    c = result.counts()
    lines.append(
        f"\nSummary: {c['passed']} passed, {c['warnings']} warnings, {c['failures']} failures"
    )
    return "\n".join(lines)


def _fmt_json(result: CheckResult) -> str:
    return json.dumps(
        {
            "checks": [
                {"level": f.level, "check": f.check,
                 "file": f.file, "line": f.line, "message": f.message}
                for f in result.findings
            ],
            "summary": result.counts(),
        },
        ensure_ascii=False,
        indent=2,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check Claude/Codex skill SKILL.md files for consistency."
    )
    parser.add_argument(
        "--side", choices=["claude", "codex", "both"], default="both",
        help="Which side(s) to scan (default: both)",
    )
    parser.add_argument(
        "--skills-dir", metavar="DIR",
        help="Override skills root (scans DIR/*/SKILL.md)",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Exit non-zero on warnings too (for CI / manual audits)",
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_output",
        help="Emit results as JSON",
    )
    parser.add_argument(
        "--all-skills", action="store_true", dest="all_skills",
        help="Scan every SKILL.md found (default: only the four protocol skills)",
    )
    args = parser.parse_args()

    result = run_checks(args)

    print(_fmt_json(result) if args.json_output else _fmt_text(result))

    if result.highest == "FAIL":
        sys.exit(1)
    if args.strict and result.highest == "WARN":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
