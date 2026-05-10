#!/usr/bin/env python3
"""Read-only gates for the Codex/Claude friend collaboration tools."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


CONSULT_RE = re.compile(r"^\[FRIEND_CONSULT round=(\d+)\]$")
WORK_CARD_MARKER = "[HELPER_WORK_CARD]"
REQUIRED_HANDOFF_SECTIONS = [
    "current_objective",
    "environment_commands",
    "file_map",
    "open_issues",
    "decisions_and_changes",
    "error_ledger",
    "next_actions",
    "agent_notes",
    "owner_review",
]
REQUIRED_FRONTMATTER_KEYS = [
    "project_key",
    "title",
    "updated_at",
    "canonical_path",
    "mailbox_root",
    "handoff_path",
]
WORK_CARD_FIELDS = [
    "goal",
    "mode",
    "codex",
    "claude",
    "integrator",
    "validate",
    "review-by",
    "stop-if",
]
SECRET_PATTERNS = [
    re.compile(r"(?i)\b(?:password|passwd|token|secret|api[_-]?key)\b\s*[:=]\s*['\"]?[^\s'\"`]{6,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\b(?:xox[baprs]-)[A-Za-z0-9-]{16,}\b"),
]
LEGACY_DISPATCH_MAP = {"0": "manual", "1": "auto", "2": "eager"}
TRUST_LEVELS = {"safe", "workspace", "danger"}
DISPATCH_MODES = {"manual", "auto", "eager"}


def now_ts() -> float:
    return time.time()


def parse_iso(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return dt.datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError):
        return None


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return default


def first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def read_text_arg(path: str | None) -> str:
    if not path or path == "-":
        return sys.stdin.read()
    return Path(path).expanduser().read_text(encoding="utf-8-sig")


def default_mailbox() -> Path:
    env = os.environ.get("FRIEND_MAILBOX") or os.environ.get("FRIEND_MAILBOX_ROOT")
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parent


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def host_kind() -> str:
    proc_version = Path("/proc/version")
    if proc_version.exists():
        try:
            content = proc_version.read_text(errors="replace").lower()
            if "microsoft" in content or "wsl" in content:
                return "wsl"
        except OSError:
            pass
    if os.name == "nt":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def host_id() -> str:
    import platform

    return f"{platform.node()}:{host_kind()}"


def line_number_for(text: str, start_index: int) -> int:
    return text.count("\n", 0, start_index) + 1


def scan_secrets(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            line = line_number_for(text, match.start())
            snippet = match.group(0).splitlines()[0]
            key = snippet.split("=", 1)[0].split(":", 1)[0].strip()
            hits.append(f"possible secret at line {line}: {key}")
    return hits


def resolve_modes() -> dict[str, Any]:
    env_trust = os.environ.get("FRIEND_TRUST_LEVEL", "")
    env_dispatch = os.environ.get("FRIEND_DISPATCH_MODE", "")

    if env_dispatch in DISPATCH_MODES:
        dispatch_mode = env_dispatch
    elif env_trust in LEGACY_DISPATCH_MAP:
        dispatch_mode = LEGACY_DISPATCH_MAP[env_trust]
    else:
        dispatch_mode = "auto"

    if env_trust in TRUST_LEVELS:
        trust_level = env_trust
    else:
        trust_level = "workspace"

    danger_downgraded = False
    if trust_level == "danger" and os.environ.get("FRIEND_TRUST_DANGER_ACK") != "I_UNDERSTAND":
        trust_level = "workspace"
        danger_downgraded = True

    return {
        "trust_level": trust_level,
        "dispatch_mode": dispatch_mode,
        "danger_downgraded": danger_downgraded,
        "env_trust_level": env_trust or None,
        "env_dispatch_mode": env_dispatch or None,
    }


def queue_status(mailbox: Path) -> dict[str, Any]:
    queue = mailbox / "queue"
    to_claude = queue / "to_claude"
    to_codex = queue / "to_codex"
    requests = sorted(to_claude.glob("*.md"))
    replies = sorted(to_codex.glob("*.md"))
    reply_ids = {p.stem for p in replies}
    pending = [p.stem for p in requests if p.stem not in reply_ids]
    reply_stems = [p.stem for p in replies[:20]]
    return {
        "request_count": len(requests),
        "reply_count": len(replies),
        "pending_to_claude_count": len(pending),
        "pending_to_claude": pending[:20],
        "reply_to_codex_count": len(replies),
        "reply_to_codex": reply_stems,
        # Deprecated aliases retained for older status consumers.
        "unconsumed_to_codex_count": len(replies),
        "unconsumed_to_codex": reply_stems,
    }


def watch_status(mailbox: Path) -> dict[str, Any]:
    lock = mailbox / ".bridge_watch.lock"
    data = read_json(lock, None)
    if not isinstance(data, dict):
        return {"path": str(lock), "present": lock.exists(), "status": "missing_or_invalid"}

    heartbeat_ts = parse_iso(data.get("heartbeat_at"))
    age = (now_ts() - heartbeat_ts) if heartbeat_ts is not None else None
    stale = age is None or age > 30.0
    pid = int(data.get("pid") or 0)
    same_host = data.get("host") == host_id()
    alive = process_alive(pid) if same_host else None
    if stale:
        status = "stale"
    elif alive is False:
        status = "dead_pid"
    else:
        status = "live"
    return {
        "path": str(lock),
        "present": True,
        "status": status,
        "pid": pid or None,
        "host": data.get("host"),
        "heartbeat_at": data.get("heartbeat_at"),
        "age_seconds": round(age, 3) if age is not None else None,
    }


def current_pointer(mailbox: Path) -> dict[str, Any]:
    current = mailbox / "CURRENT.md"
    if not current.exists():
        return {"present": False, "path": str(current), "canonical": None}
    values: dict[str, str] = {}
    for line in current.read_text(encoding="utf-8", errors="replace").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip().lower()] = value.strip()
    return {
        "present": True,
        "path": str(current),
        "canonical": values.get("canonical"),
        "owner": values.get("owner"),
        "expires": values.get("expires"),
    }


def failure_cache_status(state: dict[str, Any]) -> dict[str, Any]:
    cache = state.get("failure_cache")
    if not isinstance(cache, dict):
        return {"present": False, "active": False}
    skip_until_ts = parse_iso(cache.get("skip_until"))
    active = bool(skip_until_ts and now_ts() < skip_until_ts)
    return {
        "present": True,
        "active": active,
        "classification": cache.get("classification"),
        "failure_count": cache.get("failure_count"),
        "skip_until": cache.get("skip_until"),
        "ttl_seconds": cache.get("ttl_seconds"),
        "last_error_redacted": cache.get("last_error_redacted"),
    }


def cli_status(name: str, probe: bool) -> dict[str, Any]:
    path = shutil.which(name)
    info: dict[str, Any] = {"available": bool(path), "path": path}
    if not path or not probe:
        return info
    if name == "claude":
        command = [path, "-p", "--output-format", "json", "Please reply with OK only."]
    else:
        command = [path, "--version"]
    try:
        proc = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as exc:  # pragma: no cover - depends on local CLIs
        info.update({"probe_ok": False, "probe_error": str(exc)})
        return info
    info["probe_ok"] = proc.returncode == 0
    info["probe_returncode"] = proc.returncode
    info["probe_summary"] = (proc.stdout or proc.stderr or "").strip()[:200]
    return info


def recommendation(
    state: dict[str, Any],
    queue: dict[str, Any],
    failure: dict[str, Any],
    intent: str,
) -> dict[str, Any]:
    reasons: list[str] = []
    if state.get("pending_for_codex"):
        return {
            "route": "friend",
            "action": "process pending Claude reply before starting a new route",
            "reasons": ["pending_for_codex=true"],
        }
    if state.get("pending_for_claude"):
        return {
            "route": "direct_or_queue" if intent in {"self", "friend"} else intent,
            "action": "mailbox overwrite blocked; process Claude-side pending item or use queue/direct CLI",
            "reasons": ["pending_for_claude=true", "mailbox transport blocked"],
        }
    if failure.get("active"):
        reasons.append("claude_cli failure cache active; prefer queue/manual until skip_until")
    if queue.get("pending_to_claude_count"):
        reasons.append("queue has pending messages for Claude")
    route = intent
    return {
        "route": route,
        "action": f"{route} route is available; still follow the matching skill trigger",
        "reasons": reasons,
    }


def status_command(args: argparse.Namespace) -> int:
    mailbox = args.mailbox.expanduser().resolve()
    state = read_json(mailbox / ".bridge_state.json", {})
    queue = queue_status(mailbox)
    failure = failure_cache_status(state if isinstance(state, dict) else {})
    payload = {
        "mailbox": str(mailbox),
        "pending": {
            "pending_for_claude": bool(state.get("pending_for_claude")) if isinstance(state, dict) else False,
            "pending_for_codex": bool(state.get("pending_for_codex")) if isinstance(state, dict) else False,
            "sentinel_present": (mailbox / ".bridge.pending").exists(),
            "last_inbox_marker": state.get("last_inbox_marker") if isinstance(state, dict) else None,
            "last_outbox_marker": state.get("last_outbox_marker") if isinstance(state, dict) else None,
        },
        "queue": queue,
        "watch": watch_status(mailbox),
        "failure_cache": failure,
        "modes": resolve_modes(),
        "current": current_pointer(mailbox),
        "cli": {
            "claude": cli_status("claude", args.probe_cli),
            "codex": cli_status("codex", args.probe_cli),
        },
        "recommendation": recommendation(state if isinstance(state, dict) else {}, queue, failure, args.intent),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"mailbox: {payload['mailbox']}")
        print(f"pending: {payload['pending']}")
        print(f"queue pending_to_claude: {queue['pending_to_claude_count']}")
        print(f"watch: {payload['watch'].get('status')}")
        print(f"recommendation: {payload['recommendation']['route']} - {payload['recommendation']['action']}")
    return 0


def emit_check(name: str, warnings: list[str], errors: list[str], as_json: bool) -> int:
    status = "fail" if errors else ("warn" if warnings else "ok")
    payload = {"check": name, "status": status, "warnings": warnings, "errors": errors}
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"{name}: {status}")
        for item in errors:
            print(f"ERROR: {item}")
        for item in warnings:
            print(f"WARN: {item}")
    if errors:
        return 2
    if warnings:
        return 1
    return 0


def check_consult(args: argparse.Namespace) -> int:
    text = read_text_arg(args.path)
    warnings: list[str] = []
    errors: list[str] = []
    marker = first_nonempty_line(text)
    match = CONSULT_RE.match(marker)
    if not match:
        errors.append("first non-blank line must be [FRIEND_CONSULT round=N]")
    elif match.group(1) == "1":
        if "## Project Context" not in text and "## 项目交接" not in text:
            warnings.append("round=1 consult should include Project Context")

    for hit in scan_secrets(text):
        errors.append(hit)

    state = read_json(args.mailbox.expanduser().resolve() / ".bridge_state.json", {})
    pending_key = f"pending_for_{args.recipient}"
    if isinstance(state, dict) and state.get(pending_key) and not args.allow_pending:
        message = f"{pending_key}=true"
        if args.transport == "mailbox":
            errors.append(f"{message}; do not overwrite mailbox")
        else:
            warnings.append(f"{message}; avoid mailbox overwrite, use direct CLI or queue")
    return emit_check("check-consult", warnings, errors, args.json)


def section_present(text: str, section: str) -> bool:
    return bool(re.search(rf"^##\s+{re.escape(section)}\s*$", text, re.MULTILINE))


def frontmatter_keys(text: str) -> set[str]:
    if not text.startswith("---"):
        return set()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return set()
    keys: set[str] = set()
    for line in parts[1].splitlines():
        if ":" in line:
            keys.add(line.split(":", 1)[0].strip())
    return keys


def check_handoff(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser()
    text = path.read_text(encoding="utf-8-sig")
    warnings: list[str] = []
    errors: list[str] = []

    for hit in scan_secrets(text):
        errors.append(hit)

    missing_sections = [section for section in REQUIRED_HANDOFF_SECTIONS if not section_present(text, section)]
    if missing_sections:
        warnings.append(f"missing required sections: {', '.join(missing_sections)}")

    placeholders = sorted(set(re.findall(r"\{\{[^}]+\}\}", text)))
    if placeholders:
        warnings.append(f"unfilled template placeholders: {', '.join(placeholders[:8])}")

    keys = frontmatter_keys(text)
    if not keys:
        warnings.append("missing YAML-style frontmatter block")
    else:
        missing_keys = [key for key in REQUIRED_FRONTMATTER_KEYS if key not in keys]
        if missing_keys:
            warnings.append(f"missing frontmatter keys: {', '.join(missing_keys)}")

    for label in ("Background", "Goal", "Current stopping point"):
        if re.search(rf"^-\s+{re.escape(label)}:\s*$", text, re.MULTILINE):
            warnings.append(f"empty field: {label}")

    return emit_check("check-handoff", warnings, errors, args.json)


def parse_work_card(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if match:
            current = match.group(1).lower()
            fields[current] = match.group(2).strip()
        elif current and line.startswith((" ", "\t")):
            fields[current] = (fields[current] + "\n" + line.strip()).strip()
    return fields


def empty_card_value(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    return not stripped or stripped in {"<...>", "<paths/tasks>", "<owned paths/modules/tasks>"}


def normalize_path_token(token: str) -> str | None:
    token = token.strip().strip("`'\"()[]{}.,;:")
    if not token or token.upper() == "N/A" or token.startswith("<"):
        return None
    if "://" in token:
        return None
    if not any(mark in token for mark in ("/", "\\")):
        return None
    token = token.replace("\\", "/")
    token = token.rstrip("/*")
    while "//" in token:
        token = token.replace("//", "/")
    return token.rstrip("/") or None


def extract_path_tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    rough = re.split(r"[\s,;]+", value)
    tokens = {normalized for part in rough if (normalized := normalize_path_token(part))}
    return tokens


def paths_overlap(left: str, right: str) -> bool:
    if left == right:
        return True
    left_slash = left.rstrip("/") + "/"
    right_slash = right.rstrip("/") + "/"
    return left_slash.startswith(right_slash) or right_slash.startswith(left_slash)


def check_work_card(args: argparse.Namespace) -> int:
    text = read_text_arg(args.path)
    warnings: list[str] = []
    errors: list[str] = []
    if first_nonempty_line(text) != WORK_CARD_MARKER:
        errors.append("first non-blank line must be [HELPER_WORK_CARD]")

    fields = parse_work_card(text)
    missing = [field for field in WORK_CARD_FIELDS if field not in fields or empty_card_value(fields.get(field))]
    if missing:
        warnings.append(f"missing or empty fields: {', '.join(missing)}")

    codex_paths = extract_path_tokens(fields.get("codex"))
    claude_paths = extract_path_tokens(fields.get("claude"))
    overlaps = sorted(
        f"{left} <-> {right}"
        for left in codex_paths
        for right in claude_paths
        if paths_overlap(left, right)
    )
    if overlaps:
        errors.append(f"overlapping ownership paths: {', '.join(overlaps[:8])}")

    for hit in scan_secrets(text):
        errors.append(hit)

    return emit_check("check-work-card", warnings, errors, args.json)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mailbox", type=Path, default=default_mailbox())
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="print collaboration status without mutating mailbox")
    status.add_argument("--json", action="store_true")
    status.add_argument("--probe-cli", action="store_true", help="run small CLI probes; may call external tools")
    status.add_argument("--intent", choices=["self", "friend", "handoff", "helper"], default="self")

    consult = sub.add_parser("check-consult", help="validate a FRIEND_CONSULT message")
    consult.add_argument("path", nargs="?", help="message path, or stdin when omitted/-")
    consult.add_argument("--json", action="store_true")
    consult.add_argument("--recipient", choices=["claude", "codex"], default="claude")
    consult.add_argument("--transport", choices=["direct", "queue", "mailbox"], default="direct")
    consult.add_argument("--allow-pending", action="store_true")

    handoff = sub.add_parser("check-handoff", help="validate a handoff Markdown file")
    handoff.add_argument("path")
    handoff.add_argument("--json", action="store_true")

    work_card = sub.add_parser("check-work-card", help="validate a HELPER_WORK_CARD")
    work_card.add_argument("path", nargs="?", help="work-card path, or stdin when omitted/-")
    work_card.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.command == "status":
        return status_command(args)
    if args.command == "check-consult":
        return check_consult(args)
    if args.command == "check-handoff":
        return check_handoff(args)
    if args.command == "check-work-card":
        return check_work_card(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
