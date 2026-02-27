#!/usr/bin/env python3
# Build a static dashboard from `data/project_items.json` into `docs/index.html`.

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

TOKYO = timezone(timedelta(hours=9))

STATUS_ORDER = ["Inbox", "Ready", "Doing", "Blocked", "Done"]
RE_TASK_TYPE = re.compile(r"^\[(Investigate|Decide|Implement|Verify)\]\s*", re.IGNORECASE)
RE_NEXT = re.compile(r"^⏭\s*Next:", re.MULTILINE)
RE_P1 = re.compile(r"\bP1\b", re.IGNORECASE)

# === Quick Links (adjust if you rename repo/project) ===
PROJECT_V2_URL = "https://github.com/users/MariaCnightmare/projects/1"
ACTIONS_WORKFLOW_URL = "https://github.com/MariaCnightmare/My-Manager/actions/workflows/dashboard.yml"
REPO_URL = "https://github.com/MariaCnightmare/My-Manager"
ISSUES_URL = "https://github.com/MariaCnightmare/My-Manager/issues"


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def infer_type(title: str) -> str:
    m = RE_TASK_TYPE.match(title.strip())
    return (m.group(1).capitalize() if m else "Unknown")


def now_jst_str(ts: int) -> str:
    dt = datetime.fromtimestamp(ts, tz=TOKYO)
    return dt.strftime("%Y-%m-%d %H:%M JST")


def normalize_status(st: Any) -> str:
    s = (st or "(Unknown)")
    if s in STATUS_ORDER:
        return s
    return "(Unknown)"


def build_counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {s: 0 for s in STATUS_ORDER}
    counts["(Unknown)"] = 0
    for it in items:
        st = normalize_status(it.get("status"))
        counts[st] += 1
    return counts


def repo_key(it: Dict[str, Any]) -> str:
    c = it.get("content") or {}
    return (c.get("repository") or it.get("repository") or "").strip()


def repo_url(repo_full: str) -> str:
    if not repo_full:
        return ""
    return f"https://github.com/{repo_full}"


def violations(items: List[Dict[str, Any]]) -> List[str]:
    v: List[str] = []

    doing = [it for it in items if normalize_status(it.get("status")) == "Doing"]
    if len(doing) > 2:
        v.append(f"WIP超過: Doingが {len(doing)} 件（上限2）")

    blocked = [it for it in items if normalize_status(it.get("status")) == "Blocked"]
    for it in blocked:
        body = ((it.get("content") or {}).get("body") or "")
        if not RE_NEXT.search(body):
            url = ((it.get("content") or {}).get("url") or "")
            t = it.get("title") or ""
            v.append(f"Blockedに⏭ Nextが無い: {t} ({url})")

    p1 = 0
    for it in items:
        c = it.get("content") or {}
        text = f"{it.get('title','')}\n{c.get('body','')}"
        if RE_P1.search(text):
            p1 += 1
    if p1 > 1:
        v.append(f"P1超過（推定）: P1が {p1} 件（上限1）")

    return v


def sort_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    order = {s: i for i, s in enumerate(STATUS_ORDER)}

    def key(it: Dict[str, Any]) -> Tuple[int, str]:
        st = normalize_status(it.get("status"))
        return (order.get(st, 999), (it.get("title") or ""))

    return sorted(items, key=key)


def render_rows(items: List[Dict[str, Any]]) -> str:
    rows = []
    for it in items:
        c = it.get("content") or {}
        url = c.get("url") or ""
        num = c.get("number")
        repo = (c.get("repository") or "").strip()
        ttype = infer_type(it.get("title") or "")
        st = normalize_status(it.get("status"))
        title = it.get("title") or ""
        body = (c.get("body") or "").strip()

        st_class = {
            "Inbox": "st-inbox",
            "Ready": "st-ready",
            "Doing": "st-doing",
            "Blocked": "st-blocked",
            "Done": "st-done",
        }.get(st, "st-unknown")

        details_html = ""
        if body:
            details_html = (
                "<details class='details'>"
                "<summary>本文</summary>"
                f"<pre class='body'>{esc(body)}</pre>"
                "</details>"
            )

        rows.append(
            "<tr>"
            f"<td class='colStatus'><span class='pill {st_class}'>{esc(st)}</span></td>"
            f"<td class='colType'><span class='pill tp'>{esc(ttype)}</span></td>"
            f"<td class='colNum'>{esc(str(num) if num is not None else '-')}</td>"
            f"<td class='colTitle'>"
            f"<a href='{esc(url)}' target='_blank' rel='noopener noreferrer'>{esc(title)}</a>"
            f"<div class='sub'>{esc(repo)}</div>"
            f"{details_html}"
            "</td>"
            "</tr>"
        )
    return "\n".join(rows)


def render_group(items: List[Dict[str, Any]], status: str, default_open: bool) -> str:
    group = [it for it in items if normalize_status(it.get("status")) == status]
    if not group:
        return ""
    rows = render_rows(group)
    open_attr = " open" if default_open else ""
    return f"""
<details class="group"{open_attr}>
  <summary class="groupSum">
    <span class="groupName">{esc(status)}</span>
    <span class="groupCount">{len(group)}</span>
  </summary>
  <div class="tableWrap">
    <table class="itemsTable">
      <thead>
        <tr><th>Status</th><th>Type</th><th>#</th><th>Title</th></tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </div>
</details>
""".strip()


def build_repo_summary(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    acc: Dict[str, Dict[str, int]] = {}
    for it in items:
        rk = repo_key(it) or "(unknown repo)"
        st = normalize_status(it.get("status"))
        if rk not in acc:
            acc[rk] = {s: 0 for s in STATUS_ORDER}
            acc[rk]["(Unknown)"] = 0
        acc[rk][st] += 1

    out: List[Dict[str, Any]] = []
    for rk, m in acc.items():
        total = sum(m.values())
        out.append({"repo": rk, "counts": m, "total": total})

    # “一目”優先: Unknown → Blocked → Doing → total
    out.sort(
        key=lambda x: (
            -int(x["counts"].get("(Unknown)", 0)),
            -int(x["counts"].get("Blocked", 0)),
            -int(x["counts"].get("Doing", 0)),
            -int(x["total"]),
            x["repo"],
        )
    )
    return out


def render_repo_rows(repo_summ: List[Dict[str, Any]]) -> str:
    seg_keys = ["Inbox", "Ready", "Doing", "Blocked", "Done", "(Unknown)"]
    seg_class = {
        "Inbox": "seg inbox",
        "Ready": "seg ready",
        "Doing": "seg doing",
        "Blocked": "seg blocked",
        "Done": "seg done",
        "(Unknown)": "seg unknown",
    }

    rows = []
    for r in repo_summ:
        repo = r["repo"]
        total = int(r["total"])
        counts: Dict[str, int] = r["counts"]

        segs = []
        for k in seg_keys:
            n = int(counts.get(k, 0))
            if total <= 0 or n <= 0:
                continue
            w = (n / total) * 100.0
            segs.append(f"<span class='{seg_class[k]}' style='width:{w:.4f}%'></span>")

        bar = "<div class='stack'>" + "".join(segs) + "</div>" if segs else "<div class='stack'></div>"

        link = repo_url(repo) if "/" in repo and " " not in repo else ""
        repo_html = esc(repo)
        if link:
            repo_html = f"<a href='{esc(link)}' target='_blank' rel='noopener noreferrer'>{esc(repo)}</a>"

        badge = (
            f"<span class='mini'>I:{counts.get('Inbox',0)}</span>"
            f"<span class='mini'>R:{counts.get('Ready',0)}</span>"
            f"<span class='mini'>Dg:{counts.get('Doing',0)}</span>"
            f"<span class='mini'>Bl:{counts.get('Blocked',0)}</span>"
            f"<span class='mini'>Dn:{counts.get('Done',0)}</span>"
            f"<span class='mini warn'>U:{counts.get('(Unknown)',0)}</span>"
        )

        rows.append(
            "<tr>"
            f"<td class='repoCol'>{repo_html}<div class='sub small'>items: {total}</div></td>"
            f"<td class='barCol'>{bar}<div class='badges'>{badge}</div></td>"
            "</tr>"
        )
    return "\n".join(rows)


def main() -> None:
    src = read_json("data/project_items.json")
    items = src.get("items") or []
    total = int(src.get("totalCount") or len(items))
    gen_ts = int(time.time())

    items_sorted = sort_items(items)
    counts = build_counts(items_sorted)
    v = violations(items_sorted)

    cards_spec = [
        ("Inbox", "Inbox", "c-inbox"),
        ("Ready", "Ready", "c-ready"),
        ("Doing", "Doing", "c-doing"),
        ("Blocked", "Blocked", "c-blocked"),
        ("Done", "Done", "c-done"),
        ("Unknown", "(Unknown)", "c-unknown"),
    ]
    cards_html = []
    for label, key, cls in cards_spec:
        cards_html.append(
            f"<div class='card {cls}'>"
            f"<div class='k'>{esc(label)}</div>"
            f"<div class='v'>{counts.get(key, 0)}</div>"
            "</div>"
        )

    if v:
        v_items = "\n".join(f"<li>{esc(x)}</li>" for x in v)
        v_html = f"<div class='panel panel-warn'><h2>Rule Violations</h2><ul>{v_items}</ul></div>"
    else:
        v_html = "<div class='panel panel-ok'><h2>Rule Violations</h2><p>なし</p></div>"

    repo_summ = build_repo_summary(items_sorted)
    repo_rows = render_repo_rows(repo_summ)

    groups = []
    groups.append(render_group(items_sorted, "Inbox", True))
    groups.append(render_group(items_sorted, "Ready", True))
    groups.append(render_group(items_sorted, "Doing", True))
    groups.append(render_group(items_sorted, "Blocked", True))
    groups.append(render_group(items_sorted, "Done", False))
    groups.append(render_group(items_sorted, "(Unknown)", False))
    groups_html = "\n\n".join(g for g in groups if g)

    html = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>My-Manager Dashboard</title>
  <style>
    :root {{
      --bg: #0b0f17;
      --border: rgba(255,255,255,.08);
      --text: rgba(255,255,255,.92);
      --muted: rgba(255,255,255,.62);
      --muted2: rgba(255,255,255,.48);

      --inbox: #4f7cff;
      --ready: #22c55e;
      --doing: #a855f7;
      --blocked: #ef4444;
      --done: #38bdf8;
      --unknown: #f59e0b;

      --shadow: 0 10px 30px rgba(0,0,0,.35);
      --r: 14px;
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(1200px 700px at 20% -10%, rgba(79,124,255,.25), transparent 60%),
                  radial-gradient(900px 600px at 90% 10%, rgba(168,85,247,.22), transparent 60%),
                  radial-gradient(900px 600px at 50% 120%, rgba(34,197,94,.18), transparent 60%),
                  var(--bg);
      color: var(--text);
      font-family: system-ui, -apple-system, Segoe UI, sans-serif;
    }}

    .wrap {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 26px 18px 48px;
    }}

    header {{
      position: sticky;
      top: 0;
      z-index: 5;
      background: linear-gradient(to bottom, rgba(11,15,23,.92), rgba(11,15,23,.70));
      backdrop-filter: blur(10px);
      border-bottom: 1px solid var(--border);
      padding: 18px 18px;
      margin: -26px -18px 18px;
    }}

    h1 {{
      margin: 0 0 6px;
      font-size: 28px;
      letter-spacing: .2px;
    }}
    .meta {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }}
    .meta b {{ color: var(--text); font-weight: 900; }}

    .links {{
      margin-top: 10px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 10px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,.12);
      background: rgba(0,0,0,.18);
      color: rgba(255,255,255,.80);
      text-decoration: none;
      font-size: 12px;
      font-weight: 900;
    }}
    .btn:hover {{
      background: rgba(255,255,255,.06);
      border-color: rgba(255,255,255,.18);
    }}
    .btn.primary {{
      border-color: rgba(79,124,255,.35);
      color: rgba(170,200,255,.95);
    }}
    .hint {{
      color: var(--muted2);
      font-size: 12px;
      margin-left: 6px;
    }}

    .grid {{
      display: grid;
      grid-template-columns: repeat(6, minmax(120px, 1fr));
      gap: 12px;
      margin: 14px 0 10px;
    }}

    .card {{
      border: 1px solid var(--border);
      background: linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.02));
      border-radius: var(--r);
      padding: 12px 12px 10px;
      box-shadow: var(--shadow);
    }}
    .k {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .8px;
    }}
    .v {{
      font-size: 30px;
      font-weight: 900;
      margin-top: 6px;
    }}

    .c-inbox .v {{ color: var(--inbox); }}
    .c-ready .v {{ color: var(--ready); }}
    .c-doing .v {{ color: var(--doing); }}
    .c-blocked .v {{ color: var(--blocked); }}
    .c-done .v {{ color: var(--done); }}
    .c-unknown {{
      border-color: rgba(245,158,11,.35);
      background: linear-gradient(180deg, rgba(245,158,11,.12), rgba(255,255,255,.02));
    }}
    .c-unknown .v {{ color: var(--unknown); }}

    .panel {{
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 14px 14px 12px;
      margin: 14px 0 18px;
      box-shadow: var(--shadow);
      background: rgba(255,255,255,.03);
    }}
    .panel h2 {{
      margin: 0 0 10px;
      font-size: 15px;
      letter-spacing: .2px;
    }}
    .panel p, .panel li {{
      color: var(--muted);
      font-size: 13px;
    }}
    .panel-warn {{
      border-color: rgba(239,68,68,.35);
      background: linear-gradient(180deg, rgba(239,68,68,.12), rgba(255,255,255,.02));
    }}
    .panel-ok {{
      border-color: rgba(34,197,94,.28);
      background: linear-gradient(180deg, rgba(34,197,94,.10), rgba(255,255,255,.02));
    }}

    h2.section {{
      margin: 14px 0 10px;
      font-size: 16px;
      color: var(--text);
    }}

    .repoTable {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }}
    .repoTable th, .repoTable td {{
      border-bottom: 1px solid rgba(255,255,255,.06);
      padding: 12px 10px;
      vertical-align: top;
    }}
    .repoTable th {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 900;
      text-align: left;
    }}
    .repoCol {{
      width: 38%;
      word-break: break-word;
    }}
    .barCol {{
      width: 62%;
    }}
    .stack {{
      height: 10px;
      border-radius: 999px;
      background: rgba(0,0,0,.25);
      border: 1px solid rgba(255,255,255,.08);
      overflow: hidden;
      display: flex;
    }}
    .seg {{ height: 100%; display: block; }}
    .seg.inbox {{ background: rgba(79,124,255,.85); }}
    .seg.ready {{ background: rgba(34,197,94,.85); }}
    .seg.doing {{ background: rgba(168,85,247,.85); }}
    .seg.blocked {{ background: rgba(239,68,68,.85); }}
    .seg.done {{ background: rgba(56,189,248,.85); }}
    .seg.unknown {{ background: rgba(245,158,11,.90); }}

    .badges {{
      margin-top: 8px;
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}
    .mini {{
      font-size: 11px;
      color: rgba(255,255,255,.70);
      border: 1px solid rgba(255,255,255,.10);
      border-radius: 999px;
      padding: 2px 8px;
      background: rgba(0,0,0,.18);
    }}
    .mini.warn {{
      border-color: rgba(245,158,11,.30);
      color: rgba(255,215,140,.95);
    }}

    .group {{
      border: 1px solid var(--border);
      border-radius: var(--r);
      background: rgba(255,255,255,.02);
      margin: 10px 0;
      overflow: hidden;
    }}
    .groupSum {{
      list-style: none;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 12px 12px;
      cursor: pointer;
      user-select: none;
      color: var(--text);
    }}
    .groupSum::-webkit-details-marker {{ display: none; }}
    .groupName {{ font-weight: 900; letter-spacing: .2px; }}
    .groupCount {{
      color: var(--muted);
      font-weight: 900;
      font-size: 12px;
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(0,0,0,.15);
    }}

    .tableWrap {{ padding: 0 10px 10px; }}

    .itemsTable {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      margin-top: 6px;
      font-size: 13px;
    }}
    .itemsTable thead th {{
      background: rgba(0,0,0,.18);
      color: var(--muted);
      font-size: 12px;
      font-weight: 900;
      text-align: left;
      padding: 10px 10px;
      border-bottom: 1px solid var(--border);
    }}
    .itemsTable tbody td {{
      padding: 12px 10px;
      border-bottom: 1px solid rgba(255,255,255,.06);
      vertical-align: top;
    }}
    .itemsTable tbody tr:hover {{ background: rgba(255,255,255,.04); }}

    .colStatus {{ width: 120px; }}
    .colType {{ width: 120px; }}
    .colNum {{ width: 60px; color: var(--muted); }}
    .colTitle {{ width: auto; overflow: hidden; word-break: break-word; }}

    a {{
      color: rgba(130,180,255,.95);
      text-decoration: none;
    }}
    a:hover {{ text-decoration: underline; }}

    .sub {{
      color: var(--muted2);
      font-size: 12px;
      margin-top: 6px;
    }}
    .sub.small {{ margin-top: 6px; font-size: 11px; }}

    .pill {{
      display: inline-flex;
      align-items: center;
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(0,0,0,.20);
      font-size: 12px;
      font-weight: 900;
      color: var(--muted);
      white-space: nowrap;
    }}
    .tp {{ color: rgba(255,255,255,.75); }}

    .st-inbox {{ border-color: rgba(79,124,255,.35); color: rgba(140,175,255,.95); }}
    .st-ready {{ border-color: rgba(34,197,94,.35); color: rgba(140,255,190,.95); }}
    .st-doing {{ border-color: rgba(168,85,247,.35); color: rgba(220,170,255,.95); }}
    .st-blocked {{ border-color: rgba(239,68,68,.40); color: rgba(255,170,170,.95); }}
    .st-done {{ border-color: rgba(56,189,248,.35); color: rgba(170,235,255,.95); }}
    .st-unknown {{ border-color: rgba(245,158,11,.40); color: rgba(255,215,140,.98); }}

    .details {{ margin-top: 10px; }}
    .details summary {{
      cursor: pointer;
      color: var(--muted);
      font-size: 12px;
      user-select: none;
      list-style: none;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 2px 8px;
      border: 1px solid rgba(255,255,255,.10);
      border-radius: 999px;
      background: rgba(0,0,0,.16);
    }}
    .details summary::-webkit-details-marker {{ display: none; }}
    pre.body {{
      margin: 10px 0 0;
      white-space: pre-wrap;
      word-break: break-word;
      background: rgba(0,0,0,.25);
      border: 1px solid rgba(255,255,255,.08);
      border-radius: 12px;
      padding: 10px;
      color: rgba(255,255,255,.78);
      font-size: 12px;
      line-height: 1.5;
    }}

    @media (max-width: 980px) {{
      .grid {{ grid-template-columns: repeat(3, minmax(120px, 1fr)); }}
      .repoCol {{ width: 44%; }}
      .barCol {{ width: 56%; }}
    }}
    @media (max-width: 560px) {{
      .grid {{ grid-template-columns: repeat(2, minmax(120px, 1fr)); }}
      .repoCol, .barCol {{ width: auto; }}
      .hint {{ display: none; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>My-Manager Dashboard</h1>
      <div class="meta">
        Generated: <b>{esc(now_jst_str(gen_ts))}</b><br/>
        Total (reported): <b>{total}</b> / Items: <b>{len(items_sorted)}</b>
      </div>

      <div class="links">
        <a class="btn primary" href="{esc(ACTIONS_WORKFLOW_URL)}" target="_blank" rel="noopener noreferrer">更新（Actions）</a>
        <a class="btn" href="{esc(PROJECT_V2_URL)}" target="_blank" rel="noopener noreferrer">Project Board</a>
        <a class="btn" href="{esc(ISSUES_URL)}" target="_blank" rel="noopener noreferrer">Issues</a>
        <a class="btn" href="{esc(REPO_URL)}" target="_blank" rel="noopener noreferrer">Repo</a>
        <span class="hint">※ 更新は Actions → Run workflow</span>
      </div>

      <div class="grid">
        {''.join(cards_html)}
      </div>
    </header>

    {v_html}

    <h2 class="section">Repositories</h2>
    <div class="panel">
      <table class="repoTable">
        <thead><tr><th>Repository</th><th>Status composition</th></tr></thead>
        <tbody>
          {repo_rows}
        </tbody>
      </table>
    </div>

    <h2 class="section">Items</h2>
    {groups_html}
  </div>
</body>
</html>
"""

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("OK: wrote docs/index.html")


if __name__ == "__main__":
    main()
