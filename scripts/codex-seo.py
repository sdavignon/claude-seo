#!/usr/bin/env python3
"""Shell-independent entry point; uses the existing managed runtime."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import runtime


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] == 'auth-google':
        # Fixed, read-only standard-library flow. No arbitrary script/flag passthrough.
        if len(args) != 3 or args[1] != '--creds' or not Path(args[2]).is_file():
            print('Usage: codex-seo.py auth-google --creds EXISTING_CLIENT_JSON', file=sys.stderr)
            return 2
        return subprocess.call([
            sys.executable, str(Path(__file__).resolve().with_name('google_auth.py')),
            '--auth', '--read-only', '--creds', args[2],
        ])
    if args and args[0] == "validate-schema":
        if len(args) != 2 or not Path(args[1]).is_file():
            print("Usage: codex-seo.py validate-schema EXISTING_FILE", file=sys.stderr)
            return 2
        # This validator uses only the standard library. It is explicit, not a hook.
        return subprocess.call([
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "hooks" / "validate-schema.py"),
            args[1],
        ])
    return runtime.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
