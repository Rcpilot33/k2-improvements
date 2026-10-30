#!/usr/bin/env python3
"""Select the maintained K2 fork without replacing printer configuration."""

import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

ORIGIN = "https://github.com/Rcpilot33/moonraker.git"
BRANCH = "k2"


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], stderr=subprocess.STDOUT,
        text=True, timeout=120,
    ).strip()


def known_origin(url):
    value = url.lower().removesuffix("/").removesuffix(".git")
    return value in {
        "https://github.com/jacob10383/moonraker",
        "https://github.com/rcpilot33/moonraker",
        "git@github.com:jacob10383/moonraker",
        "git@github.com:rcpilot33/moonraker",
    }


def fork_metadata(source):
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "BASE_CONFIG":
                # Other entries contain runtime expressions; inspect only these literals.
                for key, value in zip(node.value.keys, node.value.values):
                    if isinstance(key, ast.Constant) and key.value == "moonraker":
                        return {k.value: v.value for k, v in zip(value.keys, value.values)
                                if isinstance(k, ast.Constant) and isinstance(v, ast.Constant)}
    return {}


def verify_metadata(repo, revision="HEAD"):
    source = git(repo, "show", f"{revision}:moonraker/components/update_manager/common.py")
    metadata = fork_metadata(source)
    if (metadata.get("origin") != ORIGIN or metadata.get("primary_branch") != BRANCH
            or metadata.get("channel") != "dev"):
        raise RuntimeError("The fork's k2 updater metadata is not ready; publish the matching Moonraker change first.")


def current(repo):
    try:
        return (git(repo, "remote", "get-url", "origin") == ORIGIN
                and git(repo, "branch", "--show-current") == BRANCH
                and git(repo, "rev-parse", "--abbrev-ref", "@{upstream}") == "origin/k2"
                and not git(repo, "status", "--porcelain")
                and verify_metadata(repo) is None)
    except (subprocess.SubprocessError, RuntimeError, SyntaxError):
        return False


def select_source(repo, backup_root, migrate=False):
    repo = Path(repo)
    if not repo.exists():
        if migrate:
            raise RuntimeError("No managed Moonraker checkout found; refusing to migrate stock Moonraker.")
        subprocess.run(["git", "clone", "--branch", BRANCH, "--single-branch", ORIGIN,
                        str(repo)], check=True, timeout=180)
        verify_metadata(repo)
        return
    if not known_origin(git(repo, "remote", "get-url", "origin")):
        raise RuntimeError("Unrecognized Moonraker origin; left unchanged.")
    if git(repo, "status", "--porcelain"):
        raise RuntimeError("Moonraker has local changes or untracked files; left unchanged.")
    if git(repo, "branch", "--show-current") != BRANCH:
        raise RuntimeError("Moonraker is not on k2; left unchanged.")
    old_head = git(repo, "rev-parse", "HEAD")
    git(repo, "fetch", "--no-tags", ORIGIN, "refs/heads/k2")
    target = git(repo, "rev-parse", "FETCH_HEAD")
    git(repo, "merge-base", "--is-ancestor", old_head, target)
    verify_metadata(repo, target)
    if migrate:
        # A source migration is not a dependency upgrade. Use the normal install
        # path if a future fork changes the environment requirements.
        changed = git(repo, "diff", "--name-only", old_head, target, "--", "scripts",
                      "pyproject.toml", "pdm.lock", "uv.lock")
        if changed:
            raise RuntimeError("Moonraker dependencies/install scripts changed; use a full install while idle.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    backup = Path(backup_root) / ("moonraker-source-" + stamp)
    backup.mkdir(parents=True)
    config = Path(git(repo, "rev-parse", "--absolute-git-dir")) / "config"
    shutil.copy2(config, backup / "git-config")
    (backup / "receipt.json").write_text(json.dumps({
        "old_head": old_head, "new_head": target,
        "old_origin": git(repo, "remote", "get-url", "origin"),
        "new_origin": ORIGIN, "branch": BRANCH,
    }, indent=2) + "\n", encoding="utf-8")
    # No reset, force checkout, stashing, config replacement or service control.
    # Use the already validated fetch, not a second network request that could
    # fail after changing origin or retrieve a different branch tip.
    git(repo, "update-ref", "refs/remotes/origin/k2", target)
    git(repo, "merge", "--ff-only", target)
    git(repo, "remote", "set-url", "origin", ORIGIN)
    git(repo, "branch", "--set-upstream-to=origin/k2", BRANCH)
    print(f"I: Moonraker source is {ORIGIN} ({BRANCH}); recovery receipt: {backup}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path)
    parser.add_argument("--backup-root", type=Path,
                        default=Path.home() / ".k2-improvements/repository-recovery")
    parser.add_argument("--migrate", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return 0 if current(args.repo) else 1
    try:
        select_source(args.repo, args.backup_root, args.migrate)
    except (RuntimeError, subprocess.SubprocessError, OSError) as error:
        print(f"E: Moonraker source switch failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
