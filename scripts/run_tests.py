#!/usr/bin/env python3
"""Run repository unittest suites in isolated processes to avoid module collisions."""
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main():
    directories = sorted({path.parent for folder in ("bootstrap", "features", "installer", "scripts")
                          for path in (ROOT / folder).rglob("test_*.py")})
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    failures = []
    for directory in directories:
        label = directory.relative_to(ROOT).as_posix()
        print(f"\nTesting {label}", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(directory), "-p", "test_*.py"],
            cwd=ROOT, env=env,
        )
        if result.returncode:
            failures.append(label)
    print(f"\n{len(directories)} test directories; {len(failures)} failed", flush=True)
    for failure in failures:
        print(f"FAILED: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())
