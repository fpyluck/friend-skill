#!/usr/bin/env python3
"""Minimal file queue for Codex <-> Claude friend messages.

Side-effect boundary:
- Does not call Claude/Codex APIs.
- Does not modify shell, proxy, auth, PATH, or global settings.
- Uses one request file per message and one reply file per request id.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any


REQUEST_RE = re.compile(r"^\[(?:FRIEND_CONSULT round=\d+|NOTIFY)\]$")
REPLY_RE = re.compile(r"^(AGREE[:：]|REFINE[:：]|OBJECT[:：]|ACK[:：])")


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return default


def default_mailbox() -> Path:
    env = os.environ.get("FRIEND_MAILBOX") or os.environ.get("FRIEND_MAILBOX_ROOT")
    if env:
        return Path(env).expanduser()
    return Path(__file__).resolve().parent


def queue_paths(mailbox: Path) -> dict[str, Path]:
    root = mailbox.expanduser().resolve()
    queue = root / "queue"
    return {
        "root": root,
        "queue": queue,
        "to_claude": queue / "to_claude",
        "to_codex": queue / "to_codex",
        "meta": queue / "meta.json",
    }


def request_path(paths: dict[str, Path], request_id: str) -> Path:
    return paths["to_claude"] / f"{request_id}.md"


def reply_path(paths: dict[str, Path], request_id: str) -> Path:
    return paths["to_codex"] / f"{request_id}.md"


def list_request_files(paths: dict[str, Path]) -> list[Path]:
    return sorted(paths["to_claude"].glob("*.md"))


def cmd_send(args: argparse.Namespace) -> int:
    paths = queue_paths(args.mailbox)
    text = args.message_file.read_text(encoding="utf-8-sig") if args.message_file else args.message
    if not text:
        print("empty message", file=sys.stderr)
        return 2
    marker = first_nonempty_line(text)
    if not REQUEST_RE.match(marker):
        print("message must start with [FRIEND_CONSULT round=N] or [NOTIFY]", file=sys.stderr)
        return 3
    if not text.endswith("\n"):
        text += "\n"
    digest = sha256_text(text)
    request_id = args.request_id or f"{now_stamp()}_{digest[:12]}"
    path = request_path(paths, request_id)
    if path.exists() and not args.force:
        print(f"request exists: {request_id}", file=sys.stderr)
        return 4
    atomic_write(path, text)
    meta = read_json(paths["meta"], {})
    meta.setdefault("sent", {})[request_id] = {
        "sha256": digest,
        "marker": marker,
        "created_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "path": str(path),
    }
    atomic_write(paths["meta"], json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    print(request_id)
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    paths = queue_paths(args.mailbox)
    files = list_request_files(paths)
    if not args.include_replied:
        files = [p for p in files if not reply_path(paths, p.stem).exists()]
    if not files:
        print("no pending request", file=sys.stderr)
        return 2
    path = files[0]
    if args.print_id:
        print(path.stem)
    if args.print_path:
        print(str(path))
    if args.print_body:
        text = path.read_text(encoding="utf-8-sig")
        print(text, end="" if text.endswith("\n") else "\n")
    return 0


def cmd_reply(args: argparse.Namespace) -> int:
    paths = queue_paths(args.mailbox)
    text = args.reply_file.read_text(encoding="utf-8-sig") if args.reply_file else args.reply
    if not text:
        print("empty reply", file=sys.stderr)
        return 2
    marker = first_nonempty_line(text)
    if not REPLY_RE.match(marker):
        print("reply must start with AGREE:, REFINE:, OBJECT:, or ACK:", file=sys.stderr)
        return 3
    if not request_path(paths, args.request_id).exists() and not args.force:
        print(f"unknown request id: {args.request_id}", file=sys.stderr)
        return 4
    if not text.endswith("\n"):
        text += "\n"
    path = reply_path(paths, args.request_id)
    atomic_write(path, text)
    print(str(path))
    return 0


def cmd_wait(args: argparse.Namespace) -> int:
    paths = queue_paths(args.mailbox)
    deadline = time.time() + max(args.timeout, 0)
    path = reply_path(paths, args.request_id)
    while True:
        if path.exists():
            text = path.read_text(encoding="utf-8-sig")
            marker = first_nonempty_line(text)
            if REPLY_RE.match(marker):
                print(text, end="" if text.endswith("\n") else "\n")
                return 0
            print(f"non-protocol reply for {args.request_id}: {marker}", file=sys.stderr)
            return 3
        if time.time() >= deadline:
            print(f"pending: no reply for {args.request_id} before timeout", file=sys.stderr)
            return 2
        time.sleep(args.poll_interval)


def cmd_status(args: argparse.Namespace) -> int:
    paths = queue_paths(args.mailbox)
    requests = list_request_files(paths)
    replies = sorted(paths["to_codex"].glob("*.md"))
    pending = [p.stem for p in requests if not reply_path(paths, p.stem).exists()]
    payload = {
        "mailbox": str(paths["root"]),
        "pending_count": len(pending),
        "pending": pending[:20],
        "request_count": len(requests),
        "reply_count": len(replies),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mailbox", type=Path, default=default_mailbox())
    sub = parser.add_subparsers(dest="command", required=True)

    send = sub.add_parser("send")
    src = send.add_mutually_exclusive_group(required=True)
    src.add_argument("--message")
    src.add_argument("--message-file", type=Path)
    send.add_argument("--request-id")
    send.add_argument("--force", action="store_true")

    nxt = sub.add_parser("next")
    nxt.add_argument("--include-replied", action="store_true")
    nxt.add_argument("--print-id", action="store_true")
    nxt.add_argument("--print-path", action="store_true")
    nxt.add_argument("--print-body", action="store_true")

    reply = sub.add_parser("reply")
    reply.add_argument("request_id")
    rsrc = reply.add_mutually_exclusive_group(required=True)
    rsrc.add_argument("--reply")
    rsrc.add_argument("--reply-file", type=Path)
    reply.add_argument("--force", action="store_true")

    wait = sub.add_parser("wait")
    wait.add_argument("request_id")
    wait.add_argument("--timeout", type=float, default=120.0)
    wait.add_argument("--poll-interval", type=float, default=0.5)

    sub.add_parser("status")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paths = queue_paths(args.mailbox)
    for key in ("to_claude", "to_codex"):
        paths[key].mkdir(parents=True, exist_ok=True)
    if args.command == "send":
        return cmd_send(args)
    if args.command == "next":
        return cmd_next(args)
    if args.command == "reply":
        return cmd_reply(args)
    if args.command == "wait":
        return cmd_wait(args)
    if args.command == "status":
        return cmd_status(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
