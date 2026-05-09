#!/usr/bin/env python3
"""Codex -> Claude file mailbox bridge with failure cache + watch singleton.

- mailbox path defaults to ~/.shared/friend; pass --mailbox <abs> when ~ is ambiguous (e.g. WSL with Windows-side mailbox).
- claude binary discovered via shutil.which("claude"); override with --claude-bin.
- Two locks with separate lifetimes:
    .bridge.lock        short-lived per-dispatch lock
    .bridge_watch.lock  long-lived watch singleton lock with periodic heartbeat
- Failure cache (state.failure_cache) skips dispatch within TTL after a classified failure.
  TTL base by classification (timeout=300, proxy=malformed=unknown=600, auth=900),
  exponential backoff up to 1h, env FRIEND_BRIDGE_FAILURE_TTL_SECONDS overrides base.
- Trust/dispatch control:
    FRIEND_TRUST_LEVEL = safe | workspace (default) | danger
      Controls permission flags on claude -p calls (Codex->Claude direction).
      danger requires FRIEND_TRUST_DANGER_ACK=I_UNDERSTAND else degrades to workspace.
    FRIEND_DISPATCH_MODE = manual | auto (default) | eager
      Controls automation aggressiveness for claude -p dispatch.
      Legacy FRIEND_TRUST_LEVEL=0/1/2 mapped to FRIEND_DISPATCH_MODE with deprecation warning.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PROTOCOL_RE = re.compile(r"^\[(?:FRIEND_CONSULT round=\d+|NOTIFY)\]$")
# DISPATCH_RE: only inbox markers that should trigger claude_cli auto-dispatch.
DISPATCH_RE = PROTOCOL_RE
# MAILBOX_RE: any protocol line (inbox dispatch markers OR outbox verdicts/ACKs).
# Used by manual transport to recognize a message worth full-archive + pending state.
# Accepts both ASCII colon (:) and fullwidth Chinese colon (：) after verdicts.
MAILBOX_RE = re.compile(
    r"^(\[(?:FRIEND_CONSULT round=\d+|NOTIFY)\]|AGREE[:：]|REFINE[:：]|OBJECT[:：]|ACK[:：])"
)

TTL_BASE_BY_CLASSIFICATION = {
    "timeout": 300,
    "proxy": 600,
    "malformed": 600,
    "unknown": 600,
    "auth": 900,
}
TTL_CAP = 3600
ENV_TTL_OVERRIDE = "FRIEND_BRIDGE_FAILURE_TTL_SECONDS"

# ----- trust / dispatch -----

TRUST_LEVELS = frozenset({"safe", "workspace", "danger"})
DISPATCH_MODES = frozenset({"manual", "auto", "eager"})
TRUST_LEVEL_ENV = "FRIEND_TRUST_LEVEL"
DISPATCH_MODE_ENV = "FRIEND_DISPATCH_MODE"
DANGER_ACK_ENV = "FRIEND_TRUST_DANGER_ACK"
DANGER_ACK_VALUE = "I_UNDERSTAND"
EAGER_TTL_SCALE = 0.5
EAGER_TTL_FLOOR = 30  # seconds minimum TTL after eager scaling

# claude -p allowedTools preset per trust level
TOOLS_BY_TRUST: dict[str, str] = {
    "safe": "Read,Grep,Glob,LS",
    "workspace": "Read,Grep,Glob,LS,Edit,MultiEdit,Write",
    "danger": "Read,Grep,Glob,LS,Edit,MultiEdit,Write,Bash",
}

# Legacy FRIEND_TRUST_LEVEL numeric values -> FRIEND_DISPATCH_MODE
_LEGACY_DISPATCH_MAP: dict[str, str] = {"0": "manual", "1": "auto", "2": "eager"}


# ----- helpers -----

def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def now_ts() -> float:
    return time.time()


def parse_iso(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return dt.datetime.fromisoformat(value).timestamp()
    except (ValueError, TypeError):
        return None


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def home_collapse(path: str | Path) -> str:
    home = str(Path.home())
    s = str(path)
    if s.startswith(home):
        return "~" + s[len(home):]
    return s


def redact_text(text: str, max_len: int = 80) -> str:
    if not text:
        return ""
    redacted = text.replace(str(Path.home()), "~")
    redacted = " ".join(redacted.split())
    if len(redacted) > max_len:
        redacted = redacted[: max_len - 1] + "…"
    return redacted


def detect_host_kind() -> str:
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
    return f"{platform.node()}:{detect_host_kind()}"


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (OSError, json.JSONDecodeError):
        return default


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def append_log(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event.setdefault("time", now_iso())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


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


def ttl_for_classification(classification: str, count: int, *, dispatch_mode: str = "auto") -> int:
    env_override = os.environ.get(ENV_TTL_OVERRIDE)
    base = TTL_BASE_BY_CLASSIFICATION.get(
        classification, TTL_BASE_BY_CLASSIFICATION["unknown"]
    )
    if env_override:
        try:
            base = int(env_override)
        except ValueError:
            pass
    backoff_exp = max(1, count) - 1
    ttl = base * (2 ** backoff_exp)
    ttl = min(ttl, TTL_CAP)
    # eager mode: scale down non-auth failures with a floor
    if dispatch_mode == "eager" and classification != "auth":
        ttl = max(int(ttl * EAGER_TTL_SCALE), EAGER_TTL_FLOOR)
    return ttl


def classify_failure(
    exc: Exception | None,
    completed: subprocess.CompletedProcess | None,
    payload: dict[str, Any] | None,
) -> str:
    if isinstance(exc, subprocess.TimeoutExpired):
        return "timeout"
    parts: list[str] = []
    if completed is not None:
        parts += [(completed.stdout or ""), (completed.stderr or "")]
    if payload and isinstance(payload.get("result"), str):
        parts.append(payload["result"])
    text = " ".join(parts).lower()

    api_status = (payload or {}).get("api_error_status")
    if isinstance(api_status, int) and api_status in (401, 403):
        return "auth"
    auth_keys = ("unauthor", "401", "403", "permission denied", "not logged in", "login required")
    if any(k in text for k in auth_keys):
        return "auth"
    proxy_keys = ("empty or malformed", "proxy or gateway", "http 200")
    if any(k in text for k in proxy_keys):
        return "proxy"
    if isinstance(exc, json.JSONDecodeError):
        return "malformed"
    return "unknown"


# ----- trust / dispatch resolver -----

def resolve_trust(args: argparse.Namespace) -> tuple[str, str]:
    """Return (trust_level, dispatch_mode) from CLI args + env, with validation.

    Priority: CLI arg > env var > default.
    Legacy FRIEND_TRUST_LEVEL=0/1/2 maps to FRIEND_DISPATCH_MODE with a deprecation warning.
    danger requires FRIEND_TRUST_DANGER_ACK=I_UNDERSTAND, else degrades to workspace.
    """
    env_trust_raw = os.environ.get(TRUST_LEVEL_ENV, "")
    env_dispatch = os.environ.get(DISPATCH_MODE_ENV, "")

    # --- dispatch_mode: CLI > env DISPATCH_MODE > legacy numeric > default auto ---
    if args.dispatch_mode:
        dispatch_mode = args.dispatch_mode
    elif env_dispatch in DISPATCH_MODES:
        dispatch_mode = env_dispatch
    elif env_trust_raw in _LEGACY_DISPATCH_MAP:
        migrated = _LEGACY_DISPATCH_MAP[env_trust_raw]
        print(
            f"bridge: FRIEND_TRUST_LEVEL={env_trust_raw!r} (numeric) is deprecated; "
            f"use FRIEND_DISPATCH_MODE={migrated} for automation level.",
            file=sys.stderr, flush=True,
        )
        dispatch_mode = migrated
    else:
        dispatch_mode = "auto"

    if dispatch_mode not in DISPATCH_MODES:
        print(
            f"bridge: unknown FRIEND_DISPATCH_MODE={dispatch_mode!r}, defaulting to auto",
            file=sys.stderr, flush=True,
        )
        dispatch_mode = "auto"

    # --- trust_level: CLI > env TRUST_LEVEL (named only) > default workspace ---
    if args.trust_level:
        trust_level = args.trust_level
    elif env_trust_raw in TRUST_LEVELS:
        trust_level = env_trust_raw
    else:
        if env_trust_raw and env_trust_raw not in _LEGACY_DISPATCH_MAP:
            print(
                f"bridge: unknown FRIEND_TRUST_LEVEL={env_trust_raw!r}, defaulting to workspace",
                file=sys.stderr, flush=True,
            )
        trust_level = "workspace"

    # --- danger double-confirmation gate ---
    if trust_level == "danger":
        if os.environ.get(DANGER_ACK_ENV) != DANGER_ACK_VALUE:
            print(
                f"bridge: FRIEND_TRUST_LEVEL=danger requires "
                f"{DANGER_ACK_ENV}={DANGER_ACK_VALUE!r}; degrading to workspace.",
                file=sys.stderr, flush=True,
            )
            trust_level = "workspace"

    return trust_level, dispatch_mode


# ----- locks -----

class FileLock:
    """Short-lived per-dispatch lock under <mailbox>/.bridge.lock."""

    def __init__(self, path: Path, stale_seconds: float, log_path: Path) -> None:
        self.path = path
        self.stale_seconds = stale_seconds
        self.log_path = log_path
        self.token = f"{os.getpid()}-{time.time_ns()}"
        self.acquired = False

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"pid": os.getpid(), "started_at": time.time(), "token": self.token}
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle)
                self.acquired = True
                return self
            except FileExistsError:
                if self._clear_if_stale():
                    continue
                raise RuntimeError(f"bridge lock is held: {home_collapse(self.path)}")

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if not self.acquired:
            return
        try:
            data = read_json(self.path, {})
            if data.get("token") == self.token:
                self.path.unlink(missing_ok=True)
        finally:
            self.acquired = False

    def _clear_if_stale(self) -> bool:
        data = read_json(self.path, {})
        pid = int(data.get("pid") or 0)
        started_at = float(data.get("started_at") or 0)
        age = time.time() - started_at if started_at else self.stale_seconds + 1
        if (pid and not process_alive(pid)) or age > self.stale_seconds:
            append_log(
                self.log_path,
                {"event": "stale_lock_cleared", "pid": pid, "age_seconds": round(age, 3)},
            )
            self.path.unlink(missing_ok=True)
            return True
        return False


class WatchLock:
    """Long-lived watch singleton lock with heartbeat under <mailbox>/.bridge_watch.lock."""

    def __init__(
        self,
        path: Path,
        mailbox: Path,
        poll_interval: float,
        log_path: Path,
        argv: list[str],
    ) -> None:
        self.path = path
        self.mailbox = str(mailbox)
        self.poll_interval = poll_interval
        self.log_path = log_path
        self.argv = argv
        self.acquired = False
        self.token = f"{os.getpid()}-{time.time_ns()}"
        self.stale_threshold = max(3.0 * poll_interval, 30.0)

    def _existing_alive(self) -> dict[str, Any] | None:
        data = read_json(self.path, None)
        if not isinstance(data, dict):
            return None
        if data.get("mailbox") != self.mailbox:
            return None
        heartbeat_ts = parse_iso(data.get("heartbeat_at"))
        if heartbeat_ts is None:
            return None
        if (now_ts() - heartbeat_ts) > self.stale_threshold:
            return None
        pid = int(data.get("pid") or 0)
        same_host = data.get("host") == host_id()
        if same_host and pid and not process_alive(pid):
            return None
        return data

    def acquire(self) -> tuple[bool, str]:
        existing = self._existing_alive()
        if existing is not None:
            return False, (
                f"another watcher live: pid={existing.get('pid')} "
                f"host={existing.get('host')} heartbeat_at={existing.get('heartbeat_at')}"
            )
        self._write_payload()
        verify = read_json(self.path, None)
        if not isinstance(verify, dict) or verify.get("token") != self.token:
            return False, "lock contention detected on read-back; another watcher acquired first"
        self.acquired = True
        return True, "acquired"

    def _write_payload(self) -> None:
        payload = {
            "pid": os.getpid(),
            "token": self.token,
            "host": host_id(),
            "mailbox": self.mailbox,
            "started_at": now_iso(),
            "heartbeat_at": now_iso(),
            "argv": self.argv,
        }
        atomic_write(self.path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    def heartbeat(self) -> bool:
        if not self.acquired:
            return False
        data = read_json(self.path, None)
        if not isinstance(data, dict) or data.get("token") != self.token:
            self.acquired = False
            return False
        data["heartbeat_at"] = now_iso()
        atomic_write(self.path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        return True

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            data = read_json(self.path, None)
            if isinstance(data, dict) and data.get("token") == self.token:
                self.path.unlink(missing_ok=True)
        finally:
            self.acquired = False


# ----- inbox / archive -----

def read_stable_text(path: Path, stable_delay: float) -> str | None:
    if not path.exists():
        return None
    first = path.stat()
    time.sleep(stable_delay)
    second = path.stat()
    if (first.st_size, first.st_mtime_ns) != (second.st_size, second.st_mtime_ns):
        time.sleep(stable_delay)
    return path.read_text(encoding="utf-8-sig")


def archive_pair(
    archive_dir: Path,
    digest: str,
    incoming: str,
    outgoing: str | None = None,
    *,
    metadata_only: bool = False,
    metadata: dict[str, Any] | None = None,
) -> None:
    archive_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{now_stamp()}_{digest[:12]}"
    if metadata_only:
        meta = dict(metadata or {})
        meta.update({"sha256": digest, "archived_at": now_iso()})
        atomic_write(
            archive_dir / f"{prefix}_meta.json",
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        )
        return
    atomic_write(archive_dir / f"{prefix}_codex_to_claude.md", incoming)
    if outgoing is not None:
        atomic_write(archive_dir / f"{prefix}_claude_to_codex.md", outgoing)


def archive_side(
    archive_dir: Path,
    digest: str,
    side: str,
    text: str,
    *,
    metadata_only: bool = False,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Archive a single mailbox side (codex_to_claude | claude_to_codex)."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{now_stamp()}_{digest[:12]}"
    if metadata_only:
        meta = dict(metadata or {})
        meta.update({"sha256": digest, "side": side, "archived_at": now_iso()})
        atomic_write(
            archive_dir / f"{prefix}_{side}_meta.json",
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        )
        return
    atomic_write(archive_dir / f"{prefix}_{side}.md", text)


def update_sentinel(mailbox: Path, state: dict[str, Any]) -> None:
    """Maintain ~/.shared/friend/.bridge.pending: present iff any pending flag set."""
    sentinel = mailbox / ".bridge.pending"
    pending_for_claude = bool(state.get("pending_for_claude"))
    pending_for_codex = bool(state.get("pending_for_codex"))
    if pending_for_claude or pending_for_codex:
        atomic_write(
            sentinel,
            json.dumps(
                {
                    "pending_for_claude": pending_for_claude,
                    "pending_for_codex": pending_for_codex,
                    "last_inbox_marker": state.get("last_inbox_marker"),
                    "last_outbox_marker": state.get("last_outbox_marker"),
                    "updated_at": now_iso(),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
    else:
        sentinel.unlink(missing_ok=True)


# ----- claude invocation -----

def call_claude(
    args: argparse.Namespace,
    prompt: str,
    *,
    trust_level: str = "workspace",
) -> dict[str, Any]:
    """Invoke claude -p with trust-level-derived permission flags.

    Trust-level determines the permission flags applied to the claude subprocess
    (Codex->Claude direction). User --allowed-tools override is honored when set.
    """
    command = [args.claude_bin, "-p", "--output-format", "json"]

    # Apply trust-level permission flags; honor explicit --allowed-tools override
    if trust_level == "safe":
        tools = args.allowed_tools or TOOLS_BY_TRUST["safe"]
        command.extend(["--allowedTools", tools])
    elif trust_level == "workspace":
        tools = args.allowed_tools or TOOLS_BY_TRUST["workspace"]
        command.extend(["--permission-mode", "acceptEdits", "--allowedTools", tools])
    elif trust_level == "danger":
        command.append("--dangerously-skip-permissions")
        if args.allowed_tools:
            command.extend(["--allowedTools", args.allowed_tools])

    for directory in args.add_dir:
        command.extend(["--add-dir", directory])

    try:
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=args.timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "reply": None,
            "payload": None,
            "classification": classify_failure(exc, None, None),
            "error_text": redact_text(f"timeout after {args.timeout}s"),
        }
    except FileNotFoundError as exc:
        return {
            "ok": False,
            "reply": None,
            "payload": None,
            "classification": "unknown",
            "error_text": redact_text(f"claude binary not found: {exc}"),
        }

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    if completed.returncode != 0:
        return {
            "ok": False,
            "reply": None,
            "payload": None,
            "classification": classify_failure(None, completed, None),
            "error_text": redact_text(f"exit={completed.returncode}: {stderr or stdout}"),
        }
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "reply": None,
            "payload": None,
            "classification": classify_failure(exc, completed, None),
            "error_text": redact_text(f"non-JSON: {stdout[:200]}"),
        }
    if payload.get("is_error"):
        return {
            "ok": False,
            "reply": None,
            "payload": payload,
            "classification": classify_failure(None, completed, payload),
            "error_text": redact_text(str(payload.get("result") or payload)),
        }
    result = payload.get("result")
    if not isinstance(result, str):
        return {
            "ok": False,
            "reply": None,
            "payload": payload,
            "classification": "malformed",
            "error_text": "claude JSON did not contain a string result",
        }
    return {"ok": True, "reply": result, "payload": payload, "classification": None, "error_text": None}


# ----- state migration / failure cache -----

def migrate_state(state: dict[str, Any]) -> dict[str, Any]:
    if "last_success_sha256" in state or "last_failed_sha256" in state:
        return state
    old_input = state.pop("last_input_sha256", None)
    if old_input:
        if state.get("last_status") == "ok":
            state["last_success_sha256"] = old_input
        else:
            state["last_failed_sha256"] = old_input
    return state


def cache_skip_active(state: dict[str, Any]) -> tuple[bool, dict[str, Any] | None]:
    cache = state.get("failure_cache")
    if not isinstance(cache, dict):
        return False, None
    skip_until_ts = parse_iso(cache.get("skip_until"))
    if skip_until_ts is None:
        return False, cache
    if now_ts() < skip_until_ts:
        return True, cache
    return False, cache


def make_failure_cache(
    classification: str,
    prev_cache: dict[str, Any] | None,
    error_text: str,
    *,
    dispatch_mode: str = "auto",
) -> dict[str, Any]:
    if prev_cache and prev_cache.get("classification") == classification:
        count = int(prev_cache.get("failure_count") or 0) + 1
        first = prev_cache.get("first_failure_at") or now_iso()
    else:
        count = 1
        first = now_iso()
    ttl = ttl_for_classification(classification, count, dispatch_mode=dispatch_mode)
    skip_until_ts = now_ts() + ttl
    return {
        "classification": classification,
        "first_failure_at": first,
        "last_failure_at": now_iso(),
        "failure_count": count,
        "ttl_seconds": ttl,
        "skip_until": dt.datetime.fromtimestamp(skip_until_ts, dt.timezone.utc).astimezone().isoformat(timespec="seconds"),
        "last_error_redacted": redact_text(error_text or ""),
        "dispatch_mode": dispatch_mode,
    }


# ----- manual transport tick -----

def handle_manual_tick(
    args: argparse.Namespace,
    mailbox: Path,
    inbox: Path,
    outbox: Path,
    state_path: Path,
    log_path: Path,
    archive_dir: Path,
) -> str:
    """Manual transport: protocol guard + archive + state pending flags + sentinel.

    Does NOT invoke claude. Polls inbox AND outbox; updates pending_for_{claude,codex}.
    """
    state = migrate_state(read_json(state_path, {}))
    state["transport"] = "manual"
    changed = False

    inbox_text = read_stable_text(inbox, args.stable_delay)
    if inbox_text is not None:
        in_digest = sha256_text(inbox_text)
        if state.get("last_inbox_sha256") != in_digest:
            in_marker = first_nonempty_line(inbox_text)
            in_protocol = bool(MAILBOX_RE.match(in_marker))
            archive_side(
                archive_dir,
                in_digest,
                "codex_to_claude",
                inbox_text,
                metadata_only=(args.no_archive_prompts or not in_protocol),
                metadata={
                    "marker": in_marker,
                    "is_protocol": in_protocol,
                    "summary": (inbox_text[:200] if not in_protocol else None),
                },
            )
            state["last_inbox_sha256"] = in_digest
            state["last_inbox_at"] = now_iso()
            state["last_inbox_marker"] = in_marker
            if in_protocol:
                state["pending_for_claude"] = True
                state["pending_for_codex"] = False
                append_log(
                    log_path,
                    {"event": "inbox_pending", "marker": in_marker, "sha256_short": in_digest[:12]},
                )
            else:
                append_log(
                    log_path,
                    {"event": "non_protocol_inbox", "sha256_short": in_digest[:12]},
                )
            changed = True

    outbox_text = read_stable_text(outbox, args.stable_delay)
    if outbox_text is not None:
        out_digest = sha256_text(outbox_text)
        if state.get("last_outbox_sha256") != out_digest:
            out_marker = first_nonempty_line(outbox_text)
            out_protocol = bool(MAILBOX_RE.match(out_marker))
            archive_side(
                archive_dir,
                out_digest,
                "claude_to_codex",
                outbox_text,
                metadata_only=(args.no_archive_prompts or not out_protocol),
                metadata={
                    "marker": out_marker,
                    "is_protocol": out_protocol,
                    "summary": (outbox_text[:200] if not out_protocol else None),
                },
            )
            state["last_outbox_sha256"] = out_digest
            state["last_outbox_at"] = now_iso()
            state["last_outbox_marker"] = out_marker
            if out_protocol:
                state["pending_for_codex"] = True
                state["pending_for_claude"] = False
                append_log(
                    log_path,
                    {"event": "outbox_pending", "marker": out_marker, "sha256_short": out_digest[:12]},
                )
            else:
                append_log(
                    log_path,
                    {"event": "non_protocol_outbox", "sha256_short": out_digest[:12]},
                )
            changed = True

    if changed:
        update_sentinel(mailbox, state)
        state["updated_at"] = now_iso()
        atomic_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")

    p_claude = bool(state.get("pending_for_claude"))
    p_codex = bool(state.get("pending_for_codex"))
    if p_claude and p_codex:
        return "both_pending"
    if p_claude:
        return "inbox_pending"
    if p_codex:
        return "outbox_pending"
    return "no_change"


# ----- handle_once -----

def handle_once(args: argparse.Namespace) -> str:
    mailbox = args.mailbox.expanduser().resolve()
    inbox = mailbox / "codex_to_claude.md"
    outbox = mailbox / "claude_to_codex.md"
    state_path = args.state or mailbox / ".bridge_state.json"
    log_path = args.log or mailbox / "bridge.log.jsonl"
    lock_path = args.lock or mailbox / ".bridge.lock"
    archive_dir = args.archive or mailbox / "archive"

    stale_seconds = args.stale_lock_seconds or max(args.timeout * 2, 60)
    with FileLock(lock_path, stale_seconds, log_path):
        if args.transport == "manual":
            return handle_manual_tick(
                args, mailbox, inbox, outbox, state_path, log_path, archive_dir
            )

        # claude_cli transport: resolve trust + dispatch, then original flow
        trust_level, dispatch_mode = resolve_trust(args)

        # dispatch_mode=manual: protocol guard only, no claude -p dispatch
        if dispatch_mode == "manual":
            append_log(log_path, {"event": "dispatch_disabled", "reason": "dispatch_mode=manual"})
            return handle_manual_tick(
                args, mailbox, inbox, outbox, state_path, log_path, archive_dir
            )

        message = read_stable_text(inbox, args.stable_delay)
        if message is None:
            return "missing"
        marker = first_nonempty_line(message)
        if not PROTOCOL_RE.match(marker):
            return "non-protocol"
        digest = sha256_text(message)
        state = migrate_state(read_json(state_path, {}))
        state["transport"] = "claude_cli"
        state["trust_level"] = trust_level
        state["dispatch_mode"] = dispatch_mode

        skip_active, cache = cache_skip_active(state)
        if skip_active and not args.force:
            if state.get("last_status") != "skipped_due_to_failure_cache":
                append_log(
                    log_path,
                    {
                        "event": "skipped_due_to_failure_cache",
                        "marker": marker,
                        "sha256_short": digest[:12],
                        "classification": (cache or {}).get("classification"),
                        "skip_until": (cache or {}).get("skip_until"),
                    },
                )
                state["last_status"] = "skipped_due_to_failure_cache"
                state["last_status_at"] = now_iso()
                state["updated_at"] = now_iso()
                atomic_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
            return "skipped_due_to_failure_cache"

        if not args.force and state.get("last_success_sha256") == digest:
            return "duplicate"

        append_log(
            log_path,
            {
                "event": "dispatch",
                "marker": marker,
                "sha256_short": digest[:12],
                "trust_level": trust_level,
                "dispatch_mode": dispatch_mode,
            },
        )
        outcome = call_claude(args, message, trust_level=trust_level)
        if outcome["ok"]:
            reply = outcome["reply"] or ""
            payload = outcome["payload"] or {}
            if not reply.endswith("\n"):
                reply += "\n"
            atomic_write(outbox, reply)
            archive_pair(
                archive_dir,
                digest,
                message,
                reply,
                metadata_only=args.no_archive_prompts,
                metadata={"marker": marker, "status": "ok", "session_id": payload.get("session_id")},
            )
            reply_digest = sha256_text(reply)
            state.update(
                {
                    "last_success_sha256": digest,
                    "last_inbox_sha256": digest,
                    "last_inbox_marker": marker,
                    "last_outbox_sha256": reply_digest,
                    "last_outbox_at": now_iso(),
                    "last_outbox_marker": first_nonempty_line(reply),
                    "pending_for_codex": True,
                    "pending_for_claude": False,
                    "last_status": "ok",
                    "last_status_at": now_iso(),
                    "last_marker": marker,
                    "last_session_id": payload.get("session_id"),
                    "updated_at": now_iso(),
                }
            )
            state.pop("failure_cache", None)
            update_sentinel(mailbox, state)
            atomic_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
            append_log(
                log_path,
                {"event": "wrote_reply", "sha256_short": digest[:12], "outbox": home_collapse(outbox)},
            )
            return "processed"

        classification = outcome["classification"] or "unknown"
        prev_cache = state.get("failure_cache") if isinstance(state.get("failure_cache"), dict) else None
        new_cache = make_failure_cache(
            classification, prev_cache, outcome["error_text"] or "",
            dispatch_mode=dispatch_mode,
        )
        archive_pair(
            archive_dir,
            digest,
            message,
            metadata_only=args.no_archive_prompts,
            metadata={"marker": marker, "status": "error", "classification": classification},
        )
        state.update(
            {
                "last_failed_sha256": digest,
                "last_inbox_sha256": digest,
                "last_inbox_marker": marker,
                "pending_for_claude": True,
                "last_status": "error",
                "last_status_at": now_iso(),
                "last_marker": marker,
                "failure_cache": new_cache,
                "updated_at": now_iso(),
            }
        )
        update_sentinel(mailbox, state)
        atomic_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        append_log(
            log_path,
            {
                "event": "error",
                "sha256_short": digest[:12],
                "classification": classification,
                "error_redacted": new_cache["last_error_redacted"],
                "failure_count": new_cache["failure_count"],
                "skip_until": new_cache["skip_until"],
                "trust_level": trust_level,
                "dispatch_mode": dispatch_mode,
                "claude_bin_basename": Path(args.claude_bin or "").name,
            },
        )
    return "error"


# ----- wait for manual reply -----

def wait_reply(args: argparse.Namespace) -> int:
    """Wait for Claude-side mailbox output to change, then print and consume it.

    Codex-side pull only: never invokes claude -p; never writes shell/proxy/auth.

    Baseline priority (avoids missing an already-written-but-not-yet-consumed reply
    and avoids re-consuming the same reply after a watcher tick):
      1. explicit --since-sha256 (caller knows what it last consumed)
      2. state.last_consumed_outbox_sha256 (last hash this call confirmed it consumed)
      3. live outbox hash at startup (fallback when first run on a fresh mailbox)
    """
    mailbox = args.mailbox.expanduser().resolve()
    outbox = mailbox / "claude_to_codex.md"
    state_path = args.state or mailbox / ".bridge_state.json"
    log_path = args.log or mailbox / "bridge.log.jsonl"
    lock_path = args.lock or mailbox / ".bridge.lock"
    archive_dir = args.archive or mailbox / "archive"

    initial_state = migrate_state(read_json(state_path, {}))
    if args.since_sha256:
        baseline = args.since_sha256
    elif initial_state.get("last_consumed_outbox_sha256"):
        baseline = initial_state["last_consumed_outbox_sha256"]
    else:
        existing_outbox = read_stable_text(outbox, args.stable_delay)
        baseline = sha256_text(existing_outbox) if existing_outbox is not None else ""

    deadline = now_ts() + max(args.wait_timeout, 0)
    stale_seconds = args.stale_lock_seconds or max(args.timeout * 2, 60)

    append_log(
        log_path,
        {
            "event": "wait_reply_started",
            "baseline_sha256_short": (baseline or "")[:12],
            "timeout_seconds": args.wait_timeout,
        },
    )

    while True:
        outbox_text = read_stable_text(outbox, args.stable_delay)
        if outbox_text is not None:
            digest = sha256_text(outbox_text)
            marker = first_nonempty_line(outbox_text)
            if digest != baseline and MAILBOX_RE.match(marker):
                archive_side(
                    archive_dir,
                    digest,
                    "claude_to_codex",
                    outbox_text,
                    metadata_only=args.no_archive_prompts,
                    metadata={"marker": marker, "is_protocol": True},
                )
                state_written = False
                while not state_written:
                    try:
                        with FileLock(lock_path, stale_seconds, log_path):
                            state = migrate_state(read_json(state_path, {}))
                            state["transport"] = "manual"
                            state["last_outbox_sha256"] = digest
                            state["last_outbox_at"] = now_iso()
                            state["last_outbox_marker"] = marker
                            state["last_consumed_outbox_sha256"] = digest
                            state["last_consumed_outbox_at"] = now_iso()
                            state["pending_for_codex"] = False
                            state["pending_for_claude"] = False
                            state["updated_at"] = now_iso()
                            update_sentinel(mailbox, state)
                            atomic_write(
                                state_path,
                                json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                            )
                        state_written = True
                    except RuntimeError as exc:
                        if "bridge lock is held" not in str(exc):
                            raise
                        if now_ts() >= deadline:
                            append_log(
                                log_path,
                                {"event": "wait_reply_lock_timeout", "sha256_short": digest[:12]},
                            )
                            print(
                                "wait_reply: lock contention; reply printed but state update deferred",
                                file=sys.stderr,
                            )
                            break
                        time.sleep(args.poll_interval)
                append_log(
                    log_path,
                    {"event": "wait_reply_received", "marker": marker, "sha256_short": digest[:12]},
                )
                print(outbox_text, end="" if outbox_text.endswith("\n") else "\n")
                return 0
            if digest != baseline and not MAILBOX_RE.match(marker):
                append_log(
                    log_path,
                    {"event": "wait_reply_ignored_non_protocol", "sha256_short": digest[:12]},
                )

        if now_ts() >= deadline:
            append_log(
                log_path,
                {"event": "wait_reply_timeout", "baseline_sha256_short": (baseline or "")[:12]},
            )
            print("pending: no new Claude reply before timeout", file=sys.stderr)
            return 2
        time.sleep(args.poll_interval)


# ----- probe -----

def probe_once(args: argparse.Namespace) -> int:
    """Single diagnostic call.

    transport=manual: prints status only; does not invoke claude.
    transport=claude_cli + dispatch_mode=manual: prints dispatch-disabled status.
    transport=claude_cli + dispatch_mode=auto/eager: invokes claude -p with trust-level flags.
    """
    if args.transport == "manual":
        print("transport=manual ok (no dispatch performed; bridge acts as protocol guard + archive)")
        print("hint: re-run with --transport claude_cli --probe to test claude -p")
        return 0

    trust_level, dispatch_mode = resolve_trust(args)

    if dispatch_mode == "manual":
        print(
            f"transport=claude_cli dispatch_mode=manual: dispatch disabled "
            f"(trust_level={trust_level}; probe skipped)"
        )
        print("hint: set FRIEND_DISPATCH_MODE=auto or pass --dispatch-mode auto to enable")
        return 0

    mailbox = args.mailbox.expanduser().resolve()
    state_path = args.state or mailbox / ".bridge_state.json"
    log_path = args.log or mailbox / "bridge.log.jsonl"
    state = migrate_state(read_json(state_path, {}))
    state["transport"] = "claude_cli"

    outcome = call_claude(args, "Please reply with the single word OK.", trust_level=trust_level)
    if outcome["ok"]:
        state.pop("failure_cache", None)
        state["last_probe_status"] = "ok"
        state["last_probe_at"] = now_iso()
        state["last_probe_trust_level"] = trust_level
        state["last_probe_dispatch_mode"] = dispatch_mode
        atomic_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        append_log(
            log_path,
            {
                "event": "probe_ok",
                "trust_level": trust_level,
                "dispatch_mode": dispatch_mode,
                "claude_bin_basename": Path(args.claude_bin or "").name,
            },
        )
        print(f"ok (trust_level={trust_level} dispatch_mode={dispatch_mode})")
        return 0

    classification = outcome["classification"] or "unknown"
    prev_cache = state.get("failure_cache") if isinstance(state.get("failure_cache"), dict) else None
    new_cache = make_failure_cache(
        classification, prev_cache, outcome["error_text"] or "",
        dispatch_mode=dispatch_mode,
    )
    state["failure_cache"] = new_cache
    state["last_probe_status"] = f"failed:{classification}"
    state["last_probe_at"] = now_iso()
    state["last_probe_trust_level"] = trust_level
    state["last_probe_dispatch_mode"] = dispatch_mode
    atomic_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    append_log(
        log_path,
        {
            "event": "probe_failed",
            "classification": classification,
            "error_redacted": new_cache["last_error_redacted"],
            "skip_until": new_cache["skip_until"],
            "trust_level": trust_level,
            "dispatch_mode": dispatch_mode,
            "claude_bin_basename": Path(args.claude_bin or "").name,
        },
    )
    print(f"failed:{classification} (trust_level={trust_level} dispatch_mode={dispatch_mode})")
    return 1


# ----- args / main -----

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="process inbox once then exit")
    mode.add_argument("--watch", action="store_true", help="poll inbox and process new messages")
    mode.add_argument("--probe", action="store_true", help="single diagnostic claude -p call; update failure_cache")
    mode.add_argument("--wait-reply", action="store_true", help="wait for claude_to_codex.md to receive a new protocol reply")
    parser.add_argument(
        "--transport",
        choices=["manual", "claude_cli"],
        default="manual",
        help="manual (default): protocol guard + archive + state, no claude dispatch. "
             "claude_cli: invoke claude -p (requires working claude -p; respects --dispatch-mode).",
    )
    parser.add_argument(
        "--trust-level",
        choices=["safe", "workspace", "danger"],
        default=None,
        help="Permission level for claude -p calls (Codex->Claude direction). "
             "safe=read-only; workspace=acceptEdits+write (default); danger=bypass-all+ACK required. "
             "Overrides FRIEND_TRUST_LEVEL env var.",
    )
    parser.add_argument(
        "--dispatch-mode",
        choices=["manual", "auto", "eager"],
        default=None,
        help="Automation aggressiveness for claude -p dispatch. "
             "manual=no dispatch; auto=failure_cache+TTL (default); eager=shorter TTL for transient failures. "
             "Overrides FRIEND_DISPATCH_MODE env var.",
    )
    parser.add_argument("--mailbox", type=Path, default=Path("~/.shared/friend"))
    parser.add_argument("--add-dir", action="append", default=[], help="directory Claude may read")
    parser.add_argument(
        "--allowed-tools",
        default=None,
        help="override allowedTools passed to claude -p (default derived from --trust-level). "
             "Comma-separated tool names.",
    )
    parser.add_argument("--claude-bin", default=shutil.which("claude") or "claude")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--wait-timeout", type=float, default=120.0)
    parser.add_argument(
        "--since-sha256",
        default=None,
        help="reply hash to treat as already-consumed baseline; "
             "default priority: --since-sha256 > state.last_consumed_outbox_sha256 > current outbox file hash",
    )
    parser.add_argument("--stable-delay", type=float, default=0.25)
    parser.add_argument("--stale-lock-seconds", type=float, default=None)
    parser.add_argument("--state", type=Path, default=None)
    parser.add_argument("--log", type=Path, default=None)
    parser.add_argument("--lock", type=Path, default=None)
    parser.add_argument("--watch-lock", type=Path, default=None)
    parser.add_argument("--archive", type=Path, default=None)
    parser.add_argument(
        "--no-archive-prompts",
        action="store_true",
        help="archive only metadata (skip full prompt/reply text)",
    )
    parser.add_argument("--force", action="store_true", help="bypass duplicate + failure_cache")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    mailbox = args.mailbox.expanduser().resolve()

    if args.once:
        try:
            status = handle_once(args)
        except Exception as exc:
            print(f"once: {exc}", file=sys.stderr)
            return 1
        print(status)
        return 0

    if args.probe:
        return probe_once(args)

    if args.wait_reply:
        return wait_reply(args)

    log_path = args.log or mailbox / "bridge.log.jsonl"
    watch_lock_path = args.watch_lock or mailbox / ".bridge_watch.lock"
    watch_lock = WatchLock(
        watch_lock_path,
        mailbox,
        args.poll_interval,
        log_path,
        argv=list(sys.argv),
    )
    acquired, reason = watch_lock.acquire()
    if not acquired:
        msg = f"watch singleton: {reason}; exiting cleanly"
        print(msg, flush=True)
        append_log(log_path, {"event": "watch_skip_already_running", "reason": reason})
        return 0

    # Log effective trust/dispatch at startup for claude_cli transport
    if args.transport == "claude_cli":
        trust_level, dispatch_mode = resolve_trust(args)
        startup_extra: dict[str, Any] = {"trust_level": trust_level, "dispatch_mode": dispatch_mode}
    else:
        startup_extra = {}

    print(
        f"watching {home_collapse(mailbox / 'codex_to_claude.md')} pid={os.getpid()} host={host_id()}",
        flush=True,
    )
    append_log(
        log_path,
        {
            "event": "watch_started",
            "pid": os.getpid(),
            "host": host_id(),
            "mailbox": home_collapse(mailbox),
            "claude_bin_basename": Path(args.claude_bin or "").name,
            **startup_extra,
        },
    )
    last_heartbeat = 0.0
    exit_reason = "interrupted"
    try:
        while True:
            try:
                handle_once(args)
            except Exception as exc:
                print(f"friend mailbox bridge: {exc}", file=sys.stderr, flush=True)
            if (now_ts() - last_heartbeat) >= args.poll_interval:
                if not watch_lock.heartbeat():
                    print(
                        "watch singleton: lock ownership lost; another watcher took over. exiting cleanly.",
                        file=sys.stderr,
                        flush=True,
                    )
                    append_log(
                        log_path,
                        {"event": "watch_lock_lost", "pid": os.getpid()},
                    )
                    exit_reason = "lock_lost"
                    return 0
                last_heartbeat = now_ts()
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        exit_reason = "keyboard_interrupt"
        return 130
    finally:
        watch_lock.release()
        append_log(
            log_path,
            {"event": "watch_stopped", "pid": os.getpid(), "reason": exit_reason},
        )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
