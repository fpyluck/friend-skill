#!/usr/bin/env python3
"""Shared mailbox auto-discovery for split WSL/Windows environments."""

from __future__ import annotations

import os
import sys
from pathlib import Path


SCORE_WEIGHTS: list[tuple[str, int]] = [
    (".bridge_state.json", 10),
    (".bridge.pending", 8),
    ("codex_to_claude.md", 5),
    ("claude_to_codex.md", 4),
    ("queue", 1),
]


def mailbox_score(path: Path) -> int:
    return sum(weight for name, weight in SCORE_WEIGHTS if (path / name).exists())


def is_wsl() -> bool:
    proc = Path("/proc/version")
    try:
        text = proc.read_text(errors="replace").lower()
    except OSError:
        return False
    return proc.exists() and ("microsoft" in text or "wsl" in text)


def wsl_profile_candidates() -> list[Path]:
    """Scan visible Windows profiles without shelling out."""
    found: list[Path] = []
    for drive in "cdefghijklmnopqrstuvwxyz":
        users_dir = Path(f"/mnt/{drive}/Users")
        if not users_dir.is_dir():
            continue
        try:
            profiles = sorted(users_dir.iterdir(), key=lambda p: str(p).lower())
        except PermissionError:
            continue
        for profile in profiles:
            if not profile.is_dir():
                continue
            if any((profile / marker).exists() for marker in (".claude", ".codex", ".shared")):
                found.append(profile / ".shared" / "friend")
    return found


def discover_mailbox(script_file: str | None = None) -> Path:
    """Return the best mailbox path; env vars remain explicit overrides."""
    env = os.environ.get("FRIEND_MAILBOX") or os.environ.get("FRIEND_MAILBOX_ROOT")
    if env:
        return Path(env).expanduser().resolve()

    candidates: list[Path] = [Path("~/.shared/friend").expanduser()]
    if script_file:
        script_dir = Path(script_file).resolve().parent
        candidates.append(script_dir)
        parts = script_dir.parts
        for idx, part in enumerate(parts):
            if part in (".claude", ".codex") and idx > 0:
                candidates.append(Path(*parts[:idx]) / ".shared" / "friend")
                break

    if is_wsl():
        candidates.extend(wsl_profile_candidates())

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(candidate)

    if not unique:
        return Path("~/.shared/friend").expanduser().resolve()

    scored = [(mailbox_score(candidate), index, candidate) for index, candidate in enumerate(unique)]
    scored.sort(key=lambda item: (-item[0], item[1]))
    best_score, _, best = scored[0]
    if best_score > 0 and sum(1 for score, _, _ in scored if score == best_score) > 1:
        print(
            f"friend: multiple active mailboxes (score={best_score}); "
            f"using {best}. Set FRIEND_MAILBOX to override.",
            file=sys.stderr,
        )
    return best.resolve()
