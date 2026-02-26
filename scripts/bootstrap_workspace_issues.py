#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

ISSUE_TITLE = "[Implement] Repository Inventory 2026-02"
ISSUE_BODY = """## Goal
Create a baseline inventory record for this repository.

## Checklist
- [ ] Confirm active maintainers and backup owners
- [ ] Confirm default branch and protection settings
- [ ] Confirm CI status and required checks
- [ ] Confirm release/versioning policy
- [ ] Confirm security contact and dependency update policy

## Output
- [ ] Post a short summary in this issue and link relevant docs/PRs
"""
P2_LABEL = "P2"
P2_COLOR = "FBCA04"
P2_DESCRIPTION = "Priority 2"

HTTPS_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$")
SSH_RE = re.compile(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$")

# Default exclusion to avoid self-referential noise.
EXCLUDED_REPOS = {
    "mariacnightmare/my-manager",
}


@dataclass
class RepoResult:
    path: str
    repo: str
    status: str
    message: str


def run_cmd(args: Sequence[str], cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    proc = subprocess.run(
        list(args),
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def parse_github_repo(origin: str) -> Optional[Tuple[str, str]]:
    origin = origin.strip()
    m = HTTPS_RE.match(origin)
    if not m:
        m = SSH_RE.match(origin)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    return owner, repo


def is_permission_error(stderr: str) -> bool:
    s = (stderr or "").lower()
    return any(
        key in s
        for key in [
            "403",
            "404",
            "forbidden",
            "not found",
            "resource not accessible",
            "must have",
            "authentication",
            "insufficient",
        ]
    )


def collect_git_repos(workspace: Path) -> List[Path]:
    repos: List[Path] = []
    if not workspace.exists() or not workspace.is_dir():
        return repos
    for child in sorted(workspace.iterdir()):
        if child.is_dir() and (child / ".git").exists():
            repos.append(child)
    return repos


def ensure_label(owner: str, repo: str, dry_run: bool) -> Tuple[bool, str]:
    code, out, err = run_cmd(
        [
            "gh",
            "label",
            "list",
            "--repo",
            f"{owner}/{repo}",
            "--limit",
            "200",
            "--json",
            "name",
        ]
    )
    if code != 0:
        if is_permission_error(err):
            return False, f"skip: cannot read labels ({err or 'unknown error'})"
        return False, f"failed: gh label list ({err or out or 'unknown error'})"

    try:
        labels = json.loads(out)
    except json.JSONDecodeError:
        return False, "failed: invalid JSON from gh label list"

    if any((it.get("name") == P2_LABEL) for it in labels):
        return True, "label exists"

    if dry_run:
        return True, f"dry-run: would create label {P2_LABEL}"

    code, out, err = run_cmd(
        [
            "gh",
            "label",
            "create",
            P2_LABEL,
            "--repo",
            f"{owner}/{repo}",
            "--color",
            P2_COLOR,
            "--description",
            P2_DESCRIPTION,
        ]
    )
    if code != 0:
        if "already exists" in (err or "").lower():
            return True, "label already exists"
        if is_permission_error(err):
            return False, f"skip: cannot create label ({err or 'unknown error'})"
        return False, f"failed: gh label create ({err or out or 'unknown error'})"

    return True, "label created"


def issue_exists(owner: str, repo: str) -> Tuple[bool, str]:
    query = f'in:title "{ISSUE_TITLE}"'
    code, out, err = run_cmd(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            f"{owner}/{repo}",
            "--state",
            "all",
            "--search",
            query,
            "--limit",
            "100",
            "--json",
            "title,url",
        ]
    )
    if code != 0:
        if is_permission_error(err):
            return False, f"skip: cannot read issues ({err or 'unknown error'})"
        return False, f"failed: gh issue list ({err or out or 'unknown error'})"

    try:
        issues = json.loads(out)
    except json.JSONDecodeError:
        return False, "failed: invalid JSON from gh issue list"

    for it in issues:
        if (it.get("title") or "").strip() == ISSUE_TITLE:
            return True, it.get("url") or "existing issue"
    return False, "not found"


def repo_metadata(owner: str, repo: str) -> Tuple[Optional[dict], str]:
    code, out, err = run_cmd(["gh", "api", f"repos/{owner}/{repo}"])
    if code != 0:
        if is_permission_error(err):
            return None, f"skip: no access to repo metadata ({err or 'unknown error'})"
        return None, f"failed: gh api repos/{owner}/{repo} ({err or out or 'unknown error'})"

    try:
        return json.loads(out), "ok"
    except json.JSONDecodeError:
        return None, "failed: invalid JSON from gh api"


def enable_issues(owner: str, repo: str, dry_run: bool) -> Tuple[bool, str]:
    if dry_run:
        return True, "dry-run: would enable issues"
    code, out, err = run_cmd(
        [
            "gh",
            "api",
            "-X",
            "PATCH",
            f"repos/{owner}/{repo}",
            "-f",
            "has_issues=true",
        ]
    )
    if code != 0:
        if is_permission_error(err):
            return False, f"skip: cannot enable issues ({err or 'unknown error'})"
        return False, f"failed: enabling issues ({err or out or 'unknown error'})"
    return True, "issues enabled"


def create_issue(owner: str, repo: str, dry_run: bool) -> Tuple[Optional[str], str]:
    if dry_run:
        return "dry-run://issue", "dry-run: would create issue"

    code, out, err = run_cmd(
        [
            "gh",
            "issue",
            "create",
            "--repo",
            f"{owner}/{repo}",
            "--title",
            ISSUE_TITLE,
            "--body",
            ISSUE_BODY,
            "--label",
            P2_LABEL,
        ]
    )
    if code != 0:
        if is_permission_error(err):
            return None, f"skip: cannot create issue ({err or 'unknown error'})"
        return None, f"failed: gh issue create ({err or out or 'unknown error'})"

    url = out.splitlines()[-1].strip() if out else ""
    if not url.startswith("http"):
        return None, "failed: issue URL not returned"
    return url, "issue created"


def add_to_project(project_owner: str, project_number: int, issue_url: str, dry_run: bool) -> Tuple[bool, str]:
    if dry_run:
        return True, f"dry-run: would add to project {project_owner}/{project_number}"

    code, out, err = run_cmd(
        [
            "gh",
            "project",
            "item-add",
            str(project_number),
            "--owner",
            project_owner,
            "--url",
            issue_url,
        ]
    )
    if code != 0:
        if is_permission_error(err):
            return False, f"skip: cannot add project item ({err or 'unknown error'})"
        return False, f"failed: gh project item-add ({err or out or 'unknown error'})"
    return True, "added to project"


def process_repo(path: Path, project_owner: str, project_number: int, dry_run: bool) -> RepoResult:
    code, out, err = run_cmd(["git", "remote", "get-url", "origin"], cwd=path)
    if code != 0:
        return RepoResult(str(path), "-", "skipped", f"origin unavailable ({err or out or 'unknown error'})")

    parsed = parse_github_repo(out)
    if not parsed:
        return RepoResult(str(path), "-", "skipped", f"origin is not github.com ({out})")
    owner, repo = parsed
    repo_full = f"{owner}/{repo}"

    # Exclude manager repo by default to avoid noise.
    if repo_full.lower() in EXCLUDED_REPOS:
        return RepoResult(str(path), repo_full, "skipped", "manager repo excluded")

    meta, reason = repo_metadata(owner, repo)
    if not meta:
        status = "skipped" if reason.startswith("skip:") else "failed"
        return RepoResult(str(path), repo_full, status, reason)

    if bool(meta.get("archived")):
        return RepoResult(str(path), repo_full, "skipped", "archived repository")

    if not bool(meta.get("has_issues")):
        ok, msg = enable_issues(owner, repo, dry_run)
        if not ok:
            status = "skipped" if msg.startswith("skip:") else "failed"
            return RepoResult(str(path), repo_full, status, msg)

    exists, msg = issue_exists(owner, repo)
    if msg.startswith("skip:"):
        return RepoResult(str(path), repo_full, "skipped", msg)
    if msg.startswith("failed:"):
        return RepoResult(str(path), repo_full, "failed", msg)
    if exists:
        return RepoResult(str(path), repo_full, "skipped", f"issue already exists ({msg})")

    ok, msg = ensure_label(owner, repo, dry_run)
    if not ok:
        status = "skipped" if msg.startswith("skip:") else "failed"
        return RepoResult(str(path), repo_full, status, msg)

    issue_url, msg = create_issue(owner, repo, dry_run)
    if not issue_url:
        status = "skipped" if msg.startswith("skip:") else "failed"
        return RepoResult(str(path), repo_full, status, msg)

    ok, pmsg = add_to_project(project_owner, project_number, issue_url, dry_run)
    if not ok:
        status = "skipped" if pmsg.startswith("skip:") else "failed"
        return RepoResult(str(path), repo_full, status, pmsg)

    if dry_run:
        return RepoResult(
            str(path),
            repo_full,
            "success",
            f"would create issue '{ISSUE_TITLE}' with label {P2_LABEL} and add to project {project_owner}/{project_number}",
        )

    return RepoResult(str(path), repo_full, "success", f"created issue {issue_url} and added to project")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan workspace repositories and bootstrap common inventory issues + add to Project v2."
    )
    parser.add_argument("--workspace", default="~/workspace", help="Workspace root (default: ~/workspace)")
    parser.add_argument("--project-owner", default="@me", help="Project owner (default: @me)")
    parser.add_argument("--project-number", type=int, default=1, help="Project number (default: 1)")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", dest="dry_run", action="store_true", help="Dry-run mode (default)")
    mode.add_argument("--no-dry-run", dest="dry_run", action="store_false", help="Execute changes")
    parser.set_defaults(dry_run=True)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = Path(os.path.expanduser(args.workspace)).resolve()

    repos = collect_git_repos(workspace)
    print(f"Workspace: {workspace}")
    print(f"Project: owner={args.project_owner}, number={args.project_number}")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'EXECUTE'}")
    print(f"Target directories with .git: {len(repos)}")

    if not repos:
        print("No repositories found.")
        return 0

    results: List[RepoResult] = []
    for repo_path in repos:
        res = process_repo(repo_path, args.project_owner, args.project_number, args.dry_run)
        results.append(res)
        print(f"[{res.status.upper()}] {res.path} ({res.repo}) - {res.message}")

    success = [r for r in results if r.status == "success"]
    skipped = [r for r in results if r.status == "skipped"]
    failed = [r for r in results if r.status == "failed"]

    print("\n=== Summary ===")
    print(f"success: {len(success)}")
    print(f"skipped: {len(skipped)}")
    print(f"failed: {len(failed)}")

    if skipped:
        print("\nSkipped:")
        for r in skipped:
            print(f"- {r.path} ({r.repo}): {r.message}")

    if failed:
        print("\nFailed:")
        for r in failed:
            print(f"- {r.path} ({r.repo}): {r.message}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
