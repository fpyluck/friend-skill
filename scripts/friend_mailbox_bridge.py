#!/usr/bin/env python3
"""Automate the Codex -> Claude file mailbox with a small safety gate."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PROTOCOL_RE = re.compile(r"^\[(?:FRIEND_CONSULT round=\d+|NOTIFY)\]$")


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except Exception:
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


class FileLock:
    def __init__(self, path: Path, stale_seconds: float, log_path: Path) -> None:
        self.path = path
        self.stale_seconds = stale_seconds
        self.log_path = log_path
        self.token = f"{os.getpid()}-{time.time_ns()}"
        self.acquired = False

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "started_at": time.time(),
            "token": self.token,
        }
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
                raise RuntimeError(f"bridge lock is held: {self.path}")

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


def read_stable_text(path: Path, stable_delay: float) -> str | None:
    if not path.exists():
        return None
    first = path.stat()
    time.sleep(stable_delay)
    second = path.stat()
    if (first.st_size, first.st_mtime_ns) != (second.st_size, second.st_mtime_ns):
        time.sleep(stable_delay)
    return path.read_text(encoding="utf-8-sig")


def archive_pair(archive_dir: Path, digest: str, incoming: str, outgoing: str | None = None) -> None:
    archive_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{now_stamp()}_{digest[:12]}"
    atomic_write(archive_dir / f"{prefix}_codex_to_claude.md", incoming)
    if outgoing is not None:
        atomic_write(archive_dir / f"{prefix}_claude_to_codex.md", outgoing)


def run_claude(args: argparse.Namespace, prompt: str) -> tuple[str, dict[str, Any]]:
    command = [
        args.claude_bin,
        "-p",
        "--output-format",
        "json",
        f"--allowedTools={args.allowed_tools}",
    ]
    for directory in args.add_dir:
        command.extend(["--add-dir", directory])

    completed = subprocess.run(
        command,
        input=prompt,
        text=True,
        capture_output=True,
        timeout=args.timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"claude exited {completed.returncode}: {completed.stderr.strip() or completed.stdout.strip()}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"claude returned non-JSON output: {completed.stdout[:500]!r}") from exc
    if payload.get("is_error"):
        raise RuntimeError(f"claude reported an error: {payload.get('result') or payload}")
    result = payload.get("result")
    if not isinstance(result, str):
        raise RuntimeError("claude JSON did not contain a string result")
    return result, payload


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
        message = read_stable_text(inbox, args.stable_delay)
        if message is None:
            return "missing"

        marker = first_nonempty_line(message)
        if not PROTOCOL_RE.match(marker):
            return "non-protocol"

        digest = sha256_text(message)
        state = read_json(state_path, {})
        if not args.force and state.get("last_input_sha256") == digest:
            return "duplicate"

        append_log(log_path, {"event": "dispatch", "marker": marker, "sha256": digest})
        try:
            reply, payload = run_claude(args, message)
        except Exception as exc:
            archive_pair(archive_dir, digest, message)
            state.update(
                {
                    "last_input_sha256": digest,
                    "last_status": "error",
                    "last_error": str(exc),
                    "updated_at": now_iso(),
                }
            )
            atomic_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
            append_log(log_path, {"event": "error", "sha256": digest, "error": str(exc)})
            raise

        if not reply.endswith("\n"):
            reply += "\n"
        atomic_write(outbox, reply)
        archive_pair(archive_dir, digest, message, reply)
        state.update(
            {
                "last_input_sha256": digest,
                "last_output_sha256": sha256_text(reply),
                "last_status": "ok",
                "last_marker": marker,
                "last_session_id": payload.get("session_id"),
                "updated_at": now_iso(),
            }
        )
        atomic_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        append_log(log_path, {"event": "wrote_reply", "sha256": digest, "outbox": str(outbox)})
        return "processed"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="process the current inbox once")
    mode.add_argument("--watch", action="store_true", help="poll the inbox and process new messages")
    parser.add_argument("--mailbox", type=Path, default=Path("~/.shared/friend"))
    parser.add_argument("--add-dir", action="append", default=[], help="directory Claude may read")
    parser.add_argument("--allowed-tools", default="Read,Grep,Glob,LS")
    parser.add_argument("--claude-bin", default=shutil.which("claude") or "claude")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--stable-delay", type=float, default=0.25)
    parser.add_argument("--stale-lock-seconds", type=float, default=None)
    parser.add_argument("--state", type=Path, default=None)
    parser.add_argument("--log", type=Path, default=None)
    parser.add_argument("--lock", type=Path, default=None)
    parser.add_argument("--archive", type=Path, default=None)
    parser.add_argument("--force", action="store_true", help="process even if inbox hash was already handled")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.once:
        status = handle_once(args)
        print(status)
        return 0

    print(f"watching {args.mailbox.expanduser()}/codex_to_claude.md", flush=True)
    try:
        while True:
            try:
                handle_once(args)
            except Exception as exc:
                print(f"friend mailbox bridge: {exc}", file=sys.stderr, flush=True)
            time.sleep(args.poll_interval)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
