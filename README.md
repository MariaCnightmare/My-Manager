# My-Manager

個人開発のタスク台帳（GitHub Projects v2）と、進捗可視化（Dashboard）を管理するためのハブリポジトリ。

## 目的
- 公式記録の一本化（Issue / Project / WEEKLY）
- ルール遵守（WIP・優先度・Blocked時のNextなど）の監査
- ダッシュボード生成の母艦（後で `docs/` にHTML生成してPages公開）

## 使い方（最小）
1. `PROJECT_TASK_MANAGEMENT_RULEBOOK_v1.0.md` をルールとして採用
2. `WEEKLY.md` に週1で追記
3. Issueを起票する（テンプレを使用）
4. Issue/PRを Global Task Board（Projects v2）へ追加して Status を更新

## 次の実装予定
- Project items 取得 → JSONスナップショット化
- JSON → 1枚HTML（ルール違反検知つき）
- GitHub Actions で日次更新
