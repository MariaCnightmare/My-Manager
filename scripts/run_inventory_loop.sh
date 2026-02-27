#!/usr/bin/env bash
set -euo pipefail

RUNLIST="${1:-data/inventory/runlist.tsv}"

if [ ! -f "$RUNLIST" ]; then
  echo "ERROR: missing runlist: $RUNLIST" >&2
  exit 1
fi

echo "Runlist: $RUNLIST"
echo ""
echo "How to use:"
echo "1) codex を別ターミナルで起動（My-Manager で）"
echo "2) このスクリプトが表示する request ファイルを Codex に読ませて Markdown を生成"
echo "3) 生成Markdownを output_path に貼り付け"
echo "4) Enterで次へ（Issueへ反映）"
echo ""

tail -n +2 "$RUNLIST" | while IFS=$'\t' read -r repo issue_url facts_path request_path output_path; do
  echo "================================================================================"
  echo "Repo:       $repo"
  echo "Issue URL:  ${issue_url:-'(none)'}"
  echo "Facts:      $facts_path"
  echo "Request:    $request_path"
  echo "Output:     $output_path"
  echo "--------------------------------------------------------------------------------"
  echo "REQUEST (first 120 lines):"
  sed -n '1,120p' "$request_path"
  echo "--------------------------------------------------------------------------------"
  echo "Next:"
  echo "  - codex に「$request_path を読んでテンプレ厳守でMarkdownだけ出力」"
  echo "  - 生成結果を $output_path に貼り付け保存してください"
  echo ""
  read -r -p "Press Enter AFTER you saved output file... " _

  if [ ! -f "$output_path" ]; then
    echo "SKIP: output file not found: $output_path"
    continue
  fi

  if [ -z "${issue_url:-}" ]; then
    echo "SKIP: issue_url is empty (cannot upsert)"
    continue
  fi

  scripts/upsert_issue_comment.sh "$issue_url" "$output_path"
done

echo ""
echo "DONE."
