#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def run_cmd(args: List[str]) -> Tuple[int, str, str]:
    p = subprocess.run(args, text=True, capture_output=True)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def gh_api_json(endpoint: str) -> Tuple[bool, Any, str]:
    code, out, err = run_cmd(["gh", "api", endpoint])
    if code != 0:
        return False, None, err or out or "unknown error"
    try:
        return True, json.loads(out) if out else None, ""
    except json.JSONDecodeError:
        return False, None, "invalid JSON"


def parse_iso(dt_str: str) -> Optional[datetime]:
    if not dt_str:
        return None
    # GitHub returns ISO 8601 like "2026-02-26T23:11:01Z"
    s = dt_str.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def age_days(dt: Optional[datetime], now: datetime) -> Optional[int]:
    if not dt:
        return None
    delta = now - dt
    return int(delta.total_seconds() // 86400)


def load_project_repos(project_items_path: Path) -> List[str]:
    data = json.loads(project_items_path.read_text(encoding="utf-8"))
    items = data.get("items") or []
    repos = set()
    for it in items:
        c = it.get("content") or {}
        r = (c.get("repository") or it.get("repository") or "").strip()
        # c.repository is typically "Owner/Repo"
        if r and "/" in r and " " not in r:
            repos.add(r)
    return sorted(repos)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-items", default="data/project_items.json")
    ap.add_argument("--out", default="data/repos_meta.json")
    ap.add_argument("--max-branches", type=int, default=8)
    args = ap.parse_args()

    project_items = Path(args.project_items)
    out_path = Path(args.out)

    if not project_items.exists():
        print(f"ERROR: missing {project_items}")
        return 1

    now = datetime.now(timezone.utc)
    repos = load_project_repos(project_items)

    result: Dict[str, Any] = {
        "generated_at": now.isoformat(),
        "repos": {},
        "notes": {
            "max_branches_per_repo": args.max_branches,
            "commit_dates_are_from_commits_api": True,
        },
    }

    for repo_full in repos:
        owner, name = repo_full.split("/", 1)
        repo_entry: Dict[str, Any] = {"repo": repo_full}

        ok, meta, err = gh_api_json(f"repos/{owner}/{name}")
        if not ok or not isinstance(meta, dict):
            repo_entry["error"] = f"repo meta fetch failed: {err}"
            result["repos"][repo_full] = repo_entry
            continue

        default_branch = meta.get("default_branch") or "main"
        pushed_at = meta.get("pushed_at") or ""
        pushed_dt = parse_iso(pushed_at)
        pushed_age = age_days(pushed_dt, now)

        repo_entry.update(
            {
                "default_branch": default_branch,
                "pushed_at": pushed_at,
                "pushed_age_days": pushed_age,
                "html_url": meta.get("html_url") or f"https://github.com/{repo_full}",
            }
        )

        # branches list
        ok, branches, err = gh_api_json(f"repos/{owner}/{name}/branches?per_page=100&page=1")
        if not ok or not isinstance(branches, list):
            repo_entry["branches_error"] = f"branches list failed: {err}"
            result["repos"][repo_full] = repo_entry
            continue

        branch_names = [b.get("name") for b in branches if isinstance(b, dict) and b.get("name")]
        total_branches = len(branch_names)

        # select branches: default first + next N-1
        selected: List[str] = []
        if default_branch in branch_names:
            selected.append(default_branch)
        for bn in branch_names:
            if bn == default_branch:
                continue
            if len(selected) >= max(1, args.max_branches):
                break
            selected.append(bn)

        # commit timestamps per selected branch
        branch_infos: List[Dict[str, Any]] = []
        for bn in selected:
            ok, commit, err = gh_api_json(f"repos/{owner}/{name}/commits/{bn}")
            if not ok or not isinstance(commit, dict):
                branch_infos.append(
                    {
                        "name": bn,
                        "error": f"commit fetch failed: {err}",
                    }
                )
                continue

            sha = (commit.get("sha") or "")[:12]
            commit_obj = commit.get("commit") or {}
            committer = commit_obj.get("committer") or {}
            author = commit_obj.get("author") or {}
            dt = parse_iso(committer.get("date") or author.get("date") or "")
            ad = age_days(dt, now)

            branch_infos.append(
                {
                    "name": bn,
                    "sha": sha,
                    "date": (dt.isoformat() if dt else ""),
                    "age_days": ad,
                }
            )

        # simple activity counters (sample-based)
        active_7 = 0
        stale_30 = 0
        for bi in branch_infos:
            ad = bi.get("age_days")
            if isinstance(ad, int):
                if ad <= 7:
                    active_7 += 1
                if ad > 30:
                    stale_30 += 1

        repo_entry["branches"] = {
            "total": total_branches,
            "sampled": len(branch_infos),
            "active_7d": active_7,
            "stale_30d": stale_30,
            "items": branch_infos,
        }

        # useful links
        repo_entry["links"] = {
            "branches": f"https://github.com/{repo_full}/branches",
            "pulls": f"https://github.com/{repo_full}/pulls",
            "actions": f"https://github.com/{repo_full}/actions",
            "network": f"https://github.com/{repo_full}/network",
        }

        result["repos"][repo_full] = repo_entry

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
