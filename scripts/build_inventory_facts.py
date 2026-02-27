#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ISSUE_TITLE = "[Implement] Repository Inventory 2026-02"


@dataclass
class CmdResult:
    code: int
    out: str
    err: str


def run(args: List[str], cwd: Optional[Path] = None) -> CmdResult:
    p = subprocess.run(args, cwd=str(cwd) if cwd else None, text=True, capture_output=True)
    return CmdResult(p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip())


def must_json(text: str) -> Any:
    return json.loads(text) if text else None


def iso_to_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def days_ago(dt: Optional[datetime], now: datetime) -> Optional[int]:
    if not dt:
        return None
    return int((now - dt).total_seconds() // 86400)


def gh_api(endpoint: str) -> Tuple[bool, Any, str]:
    r = run(["gh", "api", endpoint])
    if r.code != 0:
        return False, None, r.err or r.out or "unknown error"
    try:
        return True, must_json(r.out), ""
    except json.JSONDecodeError:
        return False, None, "invalid JSON"


def gh_issue_url(owner_repo: str) -> Optional[str]:
    r = run([
        "gh", "issue", "list",
        "-R", owner_repo,
        "--search", f'in:title "{ISSUE_TITLE}"',
        "--state", "all",
        "--json", "url,title",
        "--jq", ".[0].url",
    ])
    if r.code != 0:
        return None
    url = (r.out or "").strip()
    return url if url.startswith("http") else None


def load_project_items(path: Path) -> List[Dict[str, Any]]:
    data = must_json(path.read_text(encoding="utf-8"))
    return (data.get("items") or []) if isinstance(data, dict) else []


def item_repo_full(it: Dict[str, Any]) -> str:
    c = it.get("content") or {}
    r = (c.get("repository") or it.get("repository") or "").strip()
    return r


def item_url(it: Dict[str, Any]) -> str:
    c = it.get("content") or {}
    return (c.get("url") or "").strip()


def item_title(it: Dict[str, Any]) -> str:
    return (it.get("title") or "").strip()


def item_type(it: Dict[str, Any]) -> str:
    c = it.get("content") or {}
    return (c.get("type") or "").strip() or "Item"


def norm_status(it: Dict[str, Any]) -> str:
    s = (it.get("status") or "").strip()
    return s if s else "Unknown"


def build_repo_groups(items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    g: Dict[str, List[Dict[str, Any]]] = {}
    for it in items:
        repo = item_repo_full(it)
        if not repo or "/" not in repo:
            continue
        g.setdefault(repo, []).append(it)
    return g


def select_branches(branches: List[str], default_branch: str, max_branches: int) -> List[str]:
    out: List[str] = []
    if default_branch in branches:
        out.append(default_branch)
    for b in branches:
        if b == default_branch:
            continue
        if len(out) >= max_branches:
            break
        out.append(b)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-items", default="data/project_items.json")
    ap.add_argument("--template", default="templates/inventory_prompt.md")
    ap.add_argument("--out-dir", default="data/inventory")
    ap.add_argument("--max-branches", type=int, default=5)
    args = ap.parse_args()

    project_items_path = Path(args.project_items)
    template_path = Path(args.template)
    out_dir = Path(args.out_dir)

    if not project_items_path.exists():
        print(f"ERROR: missing {project_items_path}")
        return 1
    if not template_path.exists():
        print(f"ERROR: missing {template_path}")
        return 1

    now = datetime.now(timezone.utc)
    items = load_project_items(project_items_path)
    groups = build_repo_groups(items)

    facts_dir = out_dir / "facts"
    req_dir = out_dir / "requests"
    out_text_dir = out_dir / "generated"
    facts_dir.mkdir(parents=True, exist_ok=True)
    req_dir.mkdir(parents=True, exist_ok=True)
    out_text_dir.mkdir(parents=True, exist_ok=True)

    template = template_path.read_text(encoding="utf-8")

    runlist_rows: List[str] = []
    runlist_rows.append("\t".join(["repo", "issue_url", "facts_path", "request_path", "output_path"]))

    # stable order
    for repo_full in sorted(groups.keys()):
        owner, repo = repo_full.split("/", 1)

        # Project items summary
        repo_items = groups[repo_full]
        unknown_cnt = sum(1 for it in repo_items if norm_status(it) == "Unknown")
        blocked_cnt = sum(1 for it in repo_items if norm_status(it) == "Blocked")
        doing_cnt = sum(1 for it in repo_items if norm_status(it) == "Doing")

        lines_items: List[str] = []
        for it in repo_items:
            st = norm_status(it)
            title = item_title(it)
            typ = item_type(it)
            url = item_url(it)
            if url:
                lines_items.append(f"- [{st}] {title} ({typ}) {url}")
            else:
                lines_items.append(f"- [{st}] {title} ({typ})")

        # Repo meta
        default_branch = "main"
        last_push_days: Optional[int] = None

        ok, meta, err = gh_api(f"repos/{owner}/{repo}")
        if ok and isinstance(meta, dict):
            default_branch = meta.get("default_branch") or default_branch
            pushed_at = meta.get("pushed_at") or ""
            pushed_dt = iso_to_dt(pushed_at)
            last_push_days = days_ago(pushed_dt, now)

        # Branch samples
        branch_samples: List[str] = []
        ok, brs, err = gh_api(f"repos/{owner}/{repo}/branches?per_page=100&page=1")
        if ok and isinstance(brs, list):
            names = [b.get("name") for b in brs if isinstance(b, dict) and b.get("name")]
            picked = select_branches(names, default_branch, args.max_branches)
            for bn in picked:
                okc, c, _ = gh_api(f"repos/{owner}/{repo}/commits/{bn}")
                if okc and isinstance(c, dict):
                    sha = (c.get("sha") or "")[:7]
                    commit = c.get("commit") or {}
                    committer = (commit.get("committer") or {}).get("date") or ""
                    author = (commit.get("author") or {}).get("date") or ""
                    dt = iso_to_dt(committer or author)
                    ad = days_ago(dt, now)
                    ad_s = str(ad) if isinstance(ad, int) else "?"
                    sha_s = sha if sha else "?"
                    branch_samples.append(f"- {bn} age={ad_s} sha={sha_s}")
                else:
                    branch_samples.append(f"- {bn} age=? sha=?")

        if not branch_samples:
            branch_samples.append("- main age=? sha=?")

        issue_url = gh_issue_url(repo_full) or ""

        # Paths
        safe = repo_full.replace("/", "__")
        facts_path = facts_dir / f"{safe}.md"
        req_path = req_dir / f"{safe}.txt"
        out_path = out_text_dir / f"{safe}.md"

        # Facts text
        facts = []
        facts.append(f"Repo: {repo_full}")
        facts.append(f"Default branch: {default_branch}")
        if isinstance(last_push_days, int):
            facts.append(f"Last push (days): {last_push_days}")
        else:
            facts.append("Last push (days): n/a")
        facts.append("")
        facts.append("Branch samples:")
        facts.extend(branch_samples)
        facts.append("")
        facts.append("Project items (this repo):")
        facts.extend(lines_items if lines_items else ["- (none)"])
        facts.append("")
        facts.append("Signals:")
        facts.append(f"- Unknown items count: {unknown_cnt}")
        facts.append(f"- Blocked items count: {blocked_cnt} (Next missing: n/a)")
        facts.append(f"- Doing items count: {doing_cnt}")
        facts.append("")

        facts_path.write_text("\n".join(facts), encoding="utf-8")

        # Request = template + facts
        req_text = template.rstrip() + "\n\n" + "\n".join(facts)
        req_path.write_text(req_text, encoding="utf-8")

        runlist_rows.append("\t".join([repo_full, issue_url, str(facts_path), str(req_path), str(out_path)]))

    (out_dir / "runlist.tsv").write_text("\n".join(runlist_rows) + "\n", encoding="utf-8")
    print(f"OK: wrote {out_dir / 'runlist.tsv'}")
    print(f"OK: facts in {facts_dir}")
    print(f"OK: requests in {req_dir}")
    print(f"OK: output targets in {out_text_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
