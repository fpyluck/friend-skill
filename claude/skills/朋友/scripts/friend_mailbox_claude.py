#!/usr/bin/env python3
"""Claude-side helper for the Codex <-> Claude manual mailbox.

This helper is intentionally small: it never calls Codex or Claude APIs. It
only reads/writes the shared mailbox so ClaudeCode can react to pending work
without touching global shell, proxy, or settings state.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


# Windows console defaults to legacy code page (GBK on zh-CN); Chinese in
# state/inbox would be mangled when printed. Reconfigure stdout/stderr to
# UTF-8 with replace fallback so the helper is safe everywhere.
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name, None)
    reconfigure = getattr(_stream, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


INBOX_MARKER_RE = re.compile(r"^\[(?:FRIEND_CONSULT round=\d+|NOTIFY)\]$")
# Accept ASCII colon (:) and fullwidth Chinese colon (：) after verdict markers.
REPLY_MARKER_RE = re.compile(r"^(AGREE[:：]|REFINE[:：]|OBJECT[:：]|ACK[:：])")


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


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def sha256_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def mailbox_score(path: Path) -> int:
    score = 0
    for name, weight in (
        (".bridge_state.json", 4),
        (".bridge.pending", 3),
        ("codex_to_claude.md", 2),
        ("claude_to_codex.md", 1),
    ):
        if (path / name).exists():
            score += weight
    return score


def script_derived_mailbox() -> Path | None:
    """Find the sibling .shared/friend for an installed ~/.claude skill.

    In WSL, Path.home() is usually /home/<user>, while Claude's files may live
    under /mnt/c/Users/<user>/.claude. Prefer that sibling mailbox when present.
    """
    script = Path(__file__).resolve()
    parts = script.parts
    for idx, part in enumerate(parts):
        if part == ".claude" and idx > 0:
            user_root = Path(*parts[:idx])
            return user_root / ".shared" / "friend"
    return None


def resolve_mailbox(mailbox: Path | None) -> Path:
    if mailbox is not None:
        return mailbox.expanduser().resolve()
    env_mailbox = os.environ.get("FRIEND_MAILBOX")
    candidates: list[Path] = []
    if env_mailbox:
        candidates.append(Path(env_mailbox))
    derived = script_derived_mailbox()
    if derived is not None:
        candidates.append(derived)
    candidates.append(Path("~/.shared/friend").expanduser())

    best = max(candidates, key=mailbox_score)
    return best.resolve()


def mailbox_paths(mailbox: Path | None) -> dict[str, Path]:
    root = resolve_mailbox(mailbox)
    return {
        "root": root,
        "inbox": root / "codex_to_claude.md",
        "outbox": root / "claude_to_codex.md",
        "state": root / ".bridge_state.json",
        "pending": root / ".bridge.pending",
    }


def queue_script(paths: dict[str, Path]) -> Path:
    return paths["root"] / "friend_queue.py"


def cmd_status(args: argparse.Namespace) -> int:
    paths = mailbox_paths(args.mailbox)
    state = read_json(paths["state"], {})
    pending = read_json(paths["pending"], {})
    payload = {
        "mailbox": str(paths["root"]),
        "pending_for_claude": bool(
            pending.get("pending_for_claude") or state.get("pending_for_claude")
        ),
        "pending_for_codex": bool(
            pending.get("pending_for_codex") or state.get("pending_for_codex")
        ),
        "last_inbox_marker": pending.get("last_inbox_marker") or state.get("last_inbox_marker"),
        "last_outbox_marker": pending.get("last_outbox_marker") or state.get("last_outbox_marker"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    paths = mailbox_paths(args.mailbox)
    try:
        text = paths["inbox"].read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        print("missing inbox", flush=True)
        return 2
    marker = first_nonempty_line(text)
    if not INBOX_MARKER_RE.match(marker):
        print(f"non-protocol inbox: {marker}", flush=True)
        return 3
    print(text, end="" if text.endswith("\n") else "\n")
    return 0


def cmd_write(args: argparse.Namespace) -> int:
    paths = mailbox_paths(args.mailbox)
    text = args.reply
    if args.reply_file:
        text = args.reply_file.read_text(encoding="utf-8-sig")
    if not text:
        print("empty reply", flush=True)
        return 2
    marker = first_nonempty_line(text)
    if not REPLY_MARKER_RE.match(marker):
        print(
            "reply must start with AGREE:, REFINE:, OBJECT:, or ACK:",
            flush=True,
        )
        return 3
    if not text.endswith("\n"):
        text += "\n"
    atomic_write(paths["outbox"], text)
    print(str(paths["outbox"]))
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    paths = mailbox_paths(args.mailbox)
    deadline = time.time() + max(args.timeout, 0)
    last_reported = None
    while True:
        state = read_json(paths["state"], {})
        pending = read_json(paths["pending"], {})
        pending_for_claude = bool(
            pending.get("pending_for_claude") or state.get("pending_for_claude")
        )
        marker = pending.get("last_inbox_marker") or state.get("last_inbox_marker")
        if pending_for_claude and marker != last_reported:
            last_reported = marker
            if args.print_inbox:
                return cmd_read(args)
            print(f"pending_for_claude: {marker}", flush=True)
            return 0
        if time.time() >= deadline:
            print("no pending message before timeout", flush=True)
            return 2
        time.sleep(args.poll_interval)


def cmd_surface(args: argparse.Namespace) -> int:
    """Surface pending inbox into a prompt file for ClaudeCode to handle.

    This intentionally does not write claude_to_codex.md. It only makes pending
    work visible and deduplicated.
    """
    paths = mailbox_paths(args.mailbox)
    state_dir = paths["root"]
    surface_path = args.output or (state_dir / "CLAUDE_PENDING_INBOX.md")
    seen_path = state_dir / ".claude_surface_seen.json"
    deadline = time.time() + max(args.timeout, 0)

    while True:
        state = read_json(paths["state"], {})
        pending = read_json(paths["pending"], {})
        pending_for_claude = bool(
            pending.get("pending_for_claude") or state.get("pending_for_claude")
        )
        if pending_for_claude:
            try:
                inbox_text = paths["inbox"].read_text(encoding="utf-8-sig")
            except FileNotFoundError:
                inbox_text = ""
            marker = first_nonempty_line(inbox_text)
            if INBOX_MARKER_RE.match(marker):
                digest = sha256_text(inbox_text)
                seen = read_json(seen_path, {})
                if args.force or seen.get("last_surface_sha256") != digest:
                    body = (
                        "# Pending Codex Friend Request\n\n"
                        "ClaudeCode: read this request, reason normally, then write a protocol reply with:\n\n"
                        "```bash\n"
                        "python3 ~/.claude/skills/朋友/scripts/friend_mailbox_claude.py write --reply-file <reply.md>\n"
                        "```\n\n"
                        "Do not start a reverse FRIEND_CONSULT chain while answering this request.\n\n"
                        "---\n\n"
                        f"{inbox_text}"
                    )
                    atomic_write(surface_path, body)
                    atomic_write(
                        seen_path,
                        json.dumps(
                            {
                                "last_surface_sha256": digest,
                                "last_surface_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                "surface_path": str(surface_path),
                                "marker": marker,
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                        + "\n",
                    )
                    print(str(surface_path), flush=True)
                    return 0
                print(f"already surfaced: {surface_path}", flush=True)
                return 0
        if time.time() >= deadline:
            print("no pending message before timeout", flush=True)
            return 2
        time.sleep(args.poll_interval)


def cmd_queue(args: argparse.Namespace) -> int:
    paths = mailbox_paths(args.mailbox)
    command = [
        sys.executable,
        str(queue_script(paths)),
        "--mailbox",
        str(paths["root"]),
        *args.queue_args,
    ]
    return subprocess.run(command, text=True).returncode


def parse_args() -> argparse.Namespace:
    # Shared parent so --mailbox is accepted both before and after the subcommand
    # (e.g. `helper.py --mailbox <p> status` and `helper.py status --mailbox <p>`).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--mailbox",
        type=Path,
        default=None,
        help="mailbox root; defaults to FRIEND_MAILBOX, then sibling .shared/friend of this .claude install, then ~/.shared/friend",
    )

    parser = argparse.ArgumentParser(description=__doc__, parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", parents=[common], help="print pending state as JSON")
    sub.add_parser("read", parents=[common], help="print codex_to_claude.md if protocol-valid")

    watch = sub.add_parser(
        "watch",
        parents=[common],
        help="wait until pending_for_claude is true; prints inbox by default",
    )
    watch.add_argument("--timeout", type=float, default=120.0)
    watch.add_argument("--poll-interval", type=float, default=0.5)
    # print-inbox now defaults ON (most common usage); --marker-only suppresses.
    watch.add_argument(
        "--marker-only",
        dest="print_inbox",
        action="store_false",
        help="print only the marker line instead of the full inbox text",
    )
    watch.set_defaults(print_inbox=True)

    surface = sub.add_parser(
        "surface",
        parents=[common],
        help="write pending inbox to a prompt file for ClaudeCode",
    )
    surface.add_argument("--timeout", type=float, default=0.0)
    surface.add_argument("--poll-interval", type=float, default=0.5)
    surface.add_argument("--output", type=Path, default=None)
    surface.add_argument("--force", action="store_true")

    write = sub.add_parser(
        "write",
        parents=[common],
        help="write a protocol reply to claude_to_codex.md",
    )
    source = write.add_mutually_exclusive_group(required=True)
    source.add_argument("--reply", help="reply text")
    source.add_argument("--reply-file", type=Path, help="file containing reply text")

    queue = sub.add_parser("queue", parents=[common], help="pass through to shared friend_queue.py")
    queue.add_argument("queue_args", nargs=argparse.REMAINDER)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "status":
        return cmd_status(args)
    if args.command == "read":
        return cmd_read(args)
    if args.command == "watch":
        return cmd_watch(args)
    if args.command == "surface":
        return cmd_surface(args)
    if args.command == "write":
        return cmd_write(args)
    if args.command == "queue":
        return cmd_queue(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
