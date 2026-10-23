"""Single entry point for the consolidated FIS tools."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

def main():
    if len(sys.argv) < 2 or sys.argv[1] in {"--help", "-h"}:
        print("FIS Intelligence: html <commands> | kernel <root> --out <report-directory> | mcp")
        print("HTML commands: scan --root PATH, search QUERY, stats, series, collections")
        return 0
    tool, *args = sys.argv[1:]
    if tool == "html":
        command = [sys.executable, str(ROOT / "src" / "cli.py"), *args]
    elif tool == "kernel":
        if not shutil.which("cargo"):
            print("Rust scanner requires Cargo on PATH.", file=sys.stderr)
            return 2
        command = ["cargo", "run", "--manifest-path", str(ROOT / "rust" / "Cargo.toml"), "--release", "--", *args]
    elif tool == "mcp":
        command = [sys.executable, str(ROOT / "src" / "fis_mcp_server.py"), *args]
    else:
        print(f"Unknown FIS tool: {tool}", file=sys.stderr)
        return 2
    return subprocess.call(command)

import shutil
if __name__ == "__main__":
    raise SystemExit(main())
