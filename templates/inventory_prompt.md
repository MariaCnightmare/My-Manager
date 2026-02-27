# Inventory Summary (AUTO) Generator Prompt

あなたはリポジトリ棚卸し担当です。以下の Facts から、現状を分類し、次のアクションを1つ決め、根拠とともに短くまとめてください。

## 出力フォーマット（厳守）
以下のMarkdownのみを出力してください（前後に説明文不要）。

出力はMarkdownのみ。先頭に箇条書き記号（•）は付けない。

## Inventory Summary (AUTO)

### Classification
- Activity: Hot/Warm/Stale/Dormant のいずれか
- Lifecycle: Active/Pause/Archive のいずれか
- Confidence: High/Med/Low

### Evidence
- (Factsから根拠を3〜6行)

### ⏭ Next:
- 次にやる作業を1つ（具体的に）
- 期限目安:（例: 1w / 2w / 1m）

### Notes
- 追加の気づきがあれば最大3行

## Facts
以下を根拠として使う（推測はNotesに回す）：

- Repo: <owner/repo>
- Default branch: <name>
- Last push (days): <int or n/a>
- Branch samples:
  - <branch> age=<days> sha=<short>
  - ...
- Project items (this repo):
  - [<Status>] <Title> (<Issue/PR/Draft>) <URL>
  - ...
- Signals:
  - Unknown items count: <int>
  - Blocked items count: <int> (Next missing: <int>)
  - Doing items count: <int>
