#!/usr/bin/env python3
"""Create a compact Codex/Claude project handoff skeleton."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = SKILL_DIR / "assets" / "handoff-template.md"


def run(cmd: list[str], cwd: Path) -> str:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return "N/A"
    if proc.returncode != 0:
        return "N/A"
    return proc.stdout.strip() or "N/A"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "project-handoff"


def find_mailbox_root() -> Path:
    env_root = os.environ.get("FRIEND_MAILBOX_ROOT")
    if env_root:
        return Path(env_root).expanduser()

    candidates = [
        Path("/mnt/c/Users/83233/.shared/friend"),
        Path.home() / ".shared" / "friend",
    ]
    candidates.extend(Path("/mnt/c/Users").glob("*/.shared/friend"))

    for candidate in candidates:
        if (candidate / "friend_queue.py").exists() or (candidate / ".bridge_state.json").exists():
            return candidate
    return candidates[0]


def read_canonical_pointer(mailbox_root: Path) -> str:
    current = mailbox_root / "CURRENT.md"
    if not current.exists():
        return "N/A"
    for line in current.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.lower().startswith("canonical:"):
            return line.split(":", 1)[1].strip() or "N/A"
    return "N/A"


def git_info(project_root: Path) -> tuple[str, str, str]:
    branch = run(["git", "branch", "--show-current"], project_root)
    head = run(["git", "rev-parse", "--short", "HEAD"], project_root)
    status = run(["git", "status", "--short"], project_root)
    dirty = "N/A" if status == "N/A" else ("yes" if status else "no")
    return branch, head, dirty


def render(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def sync_shared_template(mailbox_root: Path) -> Path:
    shared_template = mailbox_root / "handoffs" / "handoff-template.md"
    shared_template.parent.mkdir(parents=True, exist_ok=True)
    canonical = TEMPLATE_PATH.read_text(encoding="utf-8")
    if not shared_template.exists() or shared_template.read_text(encoding="utf-8", errors="replace") != canonical:
        shared_template.write_text(canonical, encoding="utf-8")
    return shared_template


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-key", help="Stable ASCII slug for this project")
    parser.add_argument("--title", help="Human-readable project title")
    parser.add_argument("--project-root", default=os.getcwd(), help="Absolute project root")
    parser.add_argument("--agent", default="codex", help="Agent writing the handoff")
    parser.add_argument("--target-agent", default="claude", help="Expected receiving agent")
    parser.add_argument("--mailbox-root", help="Friend mailbox root")
    parser.add_argument("--project-local", action="store_true", help="Write to <project>/.handoff/")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing handoff")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).expanduser().resolve()
    mailbox_root = Path(args.mailbox_root).expanduser().resolve() if args.mailbox_root else find_mailbox_root()

    title = args.title or project_root.name
    project_key = slugify(args.project_key or title)
    handoff_dir = project_root / ".handoff" if args.project_local else mailbox_root / "handoffs"
    handoff_path = handoff_dir / f"{project_key}.md"

    if handoff_path.exists() and not args.force:
        print(f"exists: {handoff_path}")
        print("Refusing to overwrite. Edit the file in place, or rerun with --force.")
        return 2

    branch, head, dirty = git_info(project_root)
    now = datetime.now().astimezone()
    values = {
        "project_key": project_key,
        "title": title,
        "updated_at": now.isoformat(timespec="seconds"),
        "timezone": now.tzname() or "local",
        "date": now.date().isoformat(),
        "agent": args.agent,
        "target_agent": args.target_agent,
        "project_root": str(project_root),
        "mailbox_root": str(mailbox_root),
        "handoff_path": str(handoff_path),
        "git_branch": branch,
        "git_head": head,
        "git_dirty": dirty,
        "canonical_pointer": read_canonical_pointer(mailbox_root),
    }

    handoff_dir.mkdir(parents=True, exist_ok=True)
    template_path = sync_shared_template(mailbox_root)
    template = template_path.read_text(encoding="utf-8")
    handoff_path.write_text(render(template, values), encoding="utf-8")
    print(f"created: {handoff_path}")
    print(f"template: {template_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
