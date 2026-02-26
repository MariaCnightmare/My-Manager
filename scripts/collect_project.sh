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


def build_counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {s: 0 for s in STATUS_ORDER}
    counts["(Unknown)"] = 0
    for it in items:
        st = it.get("status") or "(Unknown)"
        if st in counts:
            counts[st] += 1
        else:
            counts["(Unknown)"] += 1
    return counts


def violations(items: List[Dict[str, Any]]) -> List[str]:
    v: List[str] = []

    # WIP limit: Doing <= 2
    doing = [it for it in items if (it.get("status") == "Doing")]
    if len(doing) > 2:
        v.append(f"WIP超過: Doingが {len(doing)} 件（上限2）")

    # Blocked must have Next in body (PoC: check Issue body only)
    # ※本来は最新コメントを見るのが理想だが、まずは本文で検知
    blocked = [it for it in items if (it.get("status") == "Blocked")]
    for it in blocked:
        body = ((it.get("content") or {}).get("body") or "")
        if not RE_NEXT.search(body):
            url = ((it.get("content") or {}).get("url") or "")
            t = it.get("title") or ""
            v.append(f"Blockedに⏭ Nextが無い: {t} ({url})")

    # P1 > 1 check (PoC: detect in title/body text)
    # ※ラベル/priority fieldに切り替えたら、ここをそれに合わせて強化する
    p1 = 0
    for it in items:
        c = it.get("content") or {}
        text = f"{it.get('title','')}\n{c.get('body','')}"
        if RE_P1.search(text):
            p1 += 1
    if p1 > 1:
        v.append(f"P1超過（推定）: P1が {p1} 件（上限1）")

    return v


def render_table(items: List[Dict[str, Any]]) -> str:
    # sort by status order then title
    order = {s: i for i, s in enumerate(STATUS_ORDER)}
    def key(it: Dict[str, Any]) -> Tuple[int, str]:
        st = it.get("status") or "(Unknown)"
        return (order.get(st, 999), (it.get("title") or ""))

    rows = []
    for it in sorted(items, key=key):
        c = it.get("content") or {}
        url = c.get("url") or ""
        num = c.get("number")
        repo = c.get("repository") or ""
        ttype = infer_type(it.get("title") or "")
        st = it.get("status") or "(Unknown)"
        title = it.get("title") or ""
        body = (c.get("body") or "").strip()

        rows.append(
            "<tr>"
            f"<td class='st'>{esc(st)}</td>"
            f"<td class='tp'>{esc(ttype)}</td>"
            f"<td class='id'>{esc(str(num) if num is not None else '-')}</td>"
            f"<td class='tl'><a href='{esc(url)}' target='_blank'>{esc(title)}</a>"
            f"<div class='sub'>{esc(repo)}</div>"
            f"<details><summary class='sm'>本文</summary><pre class='body'>{esc(body)}</pre></details>"
            "</td>"
            "</tr>"
        )
    return "\n".join(rows)


def main() -> None:
    src = read_json("data/project_items.json")
    items = src.get("items") or []
    total = int(src.get("totalCount") or len(items))
    gen_ts = int(time.time())

    counts = build_counts(items)
    v = violations(items)

    cards = []
    for k in ["Inbox", "Ready", "Doing", "Blocked", "Done", "(Unknown)"]:
        cards.append(
            f"<div class='card'><div class='k'>{esc(k)}</div><div class='v'>{counts.get(k, 0)}</div></div>"
        )

    v_html = ""
    if v:
        v_items = "\n".join(f"<li>{esc(x)}</li>" for x in v)
        v_html = f"<div class='warn'><h2>Rule Violations</h2><ul>{v_items}</ul></div>"
    else:
        v_html = "<div class='ok'><h2>Rule Violations</h2><p>なし</p></div>"

    table = render_table(items)

    html = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>My-Manager Dashboard</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin: 24px; }}
    h1 {{ margin: 0 0 6px; }}
    .meta {{ color: #555; margin-bottom: 16px; }}
    .grid {{ display: grid; grid-template-columns: repeat(6, minmax(120px, 1fr)); gap: 12px; margin: 12px 0 18px; }}
    .card {{ border: 1px solid #ddd; border-radius: 12px; padding: 12px; }}
    .k {{ color: #666; font-size: 12px; }}
    .v {{ font-size: 28px; font-weight: 700; }}
    .warn {{ border: 1px solid #ffb3b3; background: #fff3f3; border-radius: 12px; padding: 12px; margin: 16px 0; }}
    .ok {{ border: 1px solid #b8e0b8; background: #f3fff3; border-radius: 12px; padding: 12px; margin: 16px 0; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
    th, td {{ border-bottom: 1px solid #eee; padding: 10px; vertical-align: top; }}
    th {{ text-align: left; color: #444; font-size: 12px; }}
    td {{ font-size: 13px; }}
    a {{ color: #0b5fff; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .sub {{ color: #666; font-size: 12px; margin-top: 4px; }}
    .sm {{ color: #444; font-size: 12px; cursor: pointer; }}
    pre.body {{ white-space: pre-wrap; word-break: break-word; background: #f7f7f7; padding: 10px; border-radius: 10px; border: 1px solid #eee; }}
    .st {{ width: 120px; }}
    .tp {{ width: 120px; }}
    .id {{ width: 60px; }}
  </style>
</head>
<body>
  <h1>My-Manager Dashboard</h1>
  <div class="meta">
    Generated: {esc(now_jst_str(gen_ts))}<br/>
    Total (reported): {total} / Items: {len(items)}
  </div>

  <div class="grid">
    {''.join(cards)}
  </div>

  {v_html}

  <h2>Items</h2>
  <table>
    <thead>
      <tr>
        <th>Status</th><th>Type</th><th>#</th><th>Title</th>
      </tr>
    </thead>
    <tbody>
      {table}
    </tbody>
  </table>
</body>
</html>
"""

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("OK: wrote docs/index.html")


if __name__ == "__main__":
    main()
