#!/usr/bin/env python3
"""Gemini leaf-helper runner for the xiongdimen skill."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading


DEFAULT_MODEL = "gemini-3-pro-preview"
DEFAULT_WORKDIR = "."
TIMEOUT_SECONDS = 600
FORCE_KILL_DELAY = 5
SUCCESS_MARKERS = ("status:", "status：")


def log(level, message):
    sys.stderr.write(f"{level}: {message}\n")
    sys.stderr.flush()


def parse_args():
    if len(sys.argv) < 2:
        log("ERROR", "Prompt required")
        sys.exit(1)
    return {
        "prompt": sys.argv[1],
        "workdir": sys.argv[2] if len(sys.argv) > 2 else DEFAULT_WORKDIR,
    }


def add_candidate(paths, candidate):
    if not candidate:
        return
    path = Path(candidate).expanduser()
    if path not in paths:
        paths.append(path)


def windows_profile_from(path):
    parts = path.parts
    for index, part in enumerate(parts):
        if part.lower() == "users" and index + 1 < len(parts):
            return Path(*parts[: index + 2])
    return None


def candidate_env_paths():
    paths = []
    add_candidate(paths, os.environ.get("XIONGDIMEN_GEMINI_ENV"))
    add_candidate(paths, os.environ.get("GEMINI_ENV"))
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        add_candidate(paths, Path(userprofile) / ".gemini" / ".env")
    add_candidate(paths, Path.home() / ".gemini" / ".env")
    for probe in (Path(__file__).resolve(), Path.cwd().resolve()):
        profile = windows_profile_from(probe)
        if profile:
            add_candidate(paths, profile / ".gemini" / ".env")
    return paths


def load_env():
    for path in candidate_env_paths():
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as file:
            for raw_line in file:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export ") :].strip()
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)
        log("INFO", f"Loaded Gemini env: {path}")
        return
    log("WARN", "No Gemini .env found; relying on existing environment or Gemini settings")


def include_dirs_arg():
    custom = os.environ.get("XIONGDIMEN_GEMINI_INCLUDE_DIRS")
    if custom:
        return custom

    paths = []
    add_candidate(paths, Path.home() / ".gemini" / "skills")
    for probe in (Path(__file__).resolve(), Path.cwd().resolve()):
        profile = windows_profile_from(probe)
        if profile:
            add_candidate(paths, profile / ".gemini" / "skills-src" / "xiongdimen")
            add_candidate(paths, profile / ".gemini" / "skills")

    existing = [str(path) for path in paths if path.exists()]
    return ",".join(existing) if existing else None


def gemini_command():
    for candidate in ("gemini", "gemini.cmd"):
        path = shutil.which(candidate)
        if path:
            prefix = ["cmd", "/c", path] if path.lower().endswith((".cmd", ".bat")) else [path]
            break
    else:
        prefix = ["gemini"]
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    command = prefix + [
        "-m",
        model,
        "-p",
        "",
        "--skip-trust",
        "--approval-mode",
        "plan",
        "--output-format",
        "text",
    ]
    include_dirs = include_dirs_arg()
    if include_dirs:
        command.extend(["--include-directories", include_dirs])
    return command


def forward_stream(stream, target):
    for line in stream:
        target.write(line)
        target.flush()


def has_usable_output(lines):
    for line in lines:
        if line.strip().lower().startswith(SUCCESS_MARKERS):
            return True
    return False


def main():
    load_env()
    args = parse_args()
    workdir = args["workdir"]
    if workdir != DEFAULT_WORKDIR:
        try:
            os.chdir(workdir)
        except FileNotFoundError:
            log("ERROR", f"Working directory not found: {workdir}")
            sys.exit(1)
        except PermissionError:
            log("ERROR", f"Permission denied: {workdir}")
            sys.exit(1)

    env = os.environ.copy()
    env.setdefault("GEMINI_CLI_TRUST_WORKSPACE", "true")
    process = None
    try:
        process = subprocess.Popen(
            gemini_command(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        stderr_thread = threading.Thread(
            target=forward_stream,
            args=(process.stderr, sys.stderr),
            daemon=True,
        )
        stderr_thread.start()
        try:
            process.stdin.write(args["prompt"])
            if not args["prompt"].endswith("\n"):
                process.stdin.write("\n")
            process.stdin.close()
        except BrokenPipeError:
            pass
        stdout_lines = []
        try:
            for line in process.stdout:
                stdout_lines.append(line)
                sys.stdout.write(line)
                sys.stdout.flush()
        except OSError:
            if process.poll() is None:
                process.kill()
                try:
                    process.wait(timeout=FORCE_KILL_DELAY)
                except subprocess.TimeoutExpired:
                    pass
            return
        returncode = process.wait(timeout=TIMEOUT_SECONDS)
        stderr_thread.join(timeout=1)
        if returncode != 0:
            if has_usable_output(stdout_lines):
                log("WARN", f"Gemini exited with status {returncode} after usable output")
                return
            log("ERROR", f"Gemini exited with status {returncode}")
            sys.exit(1)
    except subprocess.TimeoutExpired:
        log("ERROR", f"Gemini execution timeout ({TIMEOUT_SECONDS}s)")
        if process is not None:
            process.kill()
            try:
                process.wait(timeout=FORCE_KILL_DELAY)
            except subprocess.TimeoutExpired:
                pass
        sys.exit(124)
    except FileNotFoundError:
        log("ERROR", "gemini command not found in PATH")
        log("ERROR", "Please install Gemini CLI, for example: npm install -g @google/gemini-cli")
        sys.exit(127)


if __name__ == "__main__":
    main()
