"""Execute approved command-line jobs with captured output."""
from __future__ import annotations

import subprocess
from pathlib import Path


def execute_command_line(payload: dict[str, object]) -> dict[str, object]:
    command = payload.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
        raise ValueError("command must be a non-empty list of strings")
    cwd_value = payload.get("cwd")
    cwd = str(Path(str(cwd_value)).resolve()) if cwd_value else None
    timeout = float(payload.get("timeout_seconds", 60))
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "command": command,
        "cwd": cwd,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "timed_out": False,
    }
