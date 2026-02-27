#!/usr/bin/env bash
set -euo pipefail

RUNLIST="${1:-data/inventory/runlist.tsv}"
EDITOR_CMD="${EDITOR:-vi}"

if [ ! -f "$RUNLIST" ]; then
  echo "ERROR: missing runlist: $RUNLIST" >&2
  exit 1
fi

echo "Runlist: $RUNLIST"
echo ""
echo "How to use:"
echo "  - codex を別ターミナルで起動（My-Manager で）"
echo "  - このスクリプトが request/facts を表示"
echo "  - codex に request_path を読ませて Markdown を生成"
echo "  - 生成結果を editor で開く output ファイルに貼り付けて保存"
echo "  - 保存して閉じたら Issue へ自動反映（upsert）"
echo ""
echo "Editor: $EDITOR_CMD"
echo ""

ensure_output_skeleton() {
  local out="$1"
  mkdir -p "$(dirname "$out")"
  if [ -f "$out" ] && [ -s "$out" ]; then
    return 0
  fi

  cat > "$out" <<'EOF'
## Inventory Summary (AUTO)

### Classification
- Activity:
- Lifecycle:
- Confidence:

### Evidence
- 

### ⏭ Next:
- 
- 期限目安: 

### Notes
- 
EOF
}

validate_output() {
  local out="$1"

  if ! grep -q '^## Inventory Summary (AUTO)' "$out"; then
    echo "WARN: output does not contain heading '## Inventory Summary (AUTO)'."
    return 1
  fi

  # codexが先頭に「• 」を付けがちなので、ここで除去
  if grep -qE '^•\s' "$out"; then
    sed -i 's/^•[ ]\{0,1\}//' "$out"
  fi

  return 0
}

prompt_choice() {
  local prompt="$1"
  local choice=""
  while true; do
    read -r -p "$prompt [Enter=continue / s=skip / q=quit] " choice || true
    case "${choice:-}" in
      "" ) return 0 ;;
      s|S ) return 2 ;;
      q|Q ) return 3 ;;
      * ) echo "Input error. Use Enter / s / q." ;;
    esac
  done
}

# stdin をTTYに確保（パイプ等で壊れたときの保険）
TTY_IN="/dev/tty"
if [ ! -r "$TTY_IN" ]; then
  TTY_IN=""
fi

{
  read -r _header || true  # skip header

  while IFS=$'\t' read -r repo issue_url facts_path request_path output_path; do
    # 5列チェック（崩れ行ガード）
    if [ -z "${repo:-}" ] || [ -z "${facts_path:-}" ] || [ -z "${request_path:-}" ] || [ -z "${output_path:-}" ]; then
      echo "SKIP: invalid row (missing columns): repo='${repo:-}'"
      continue
    fi

    echo "================================================================================"
    echo "Repo:       $repo"
    echo "Issue URL:  ${issue_url:-'(none)'}"
    echo "Facts:      $facts_path"
    echo "Request:    $request_path"
    echo "Output:     $output_path"
    echo "--------------------------------------------------------------------------------"

    echo "[FACTS] (first 120 lines)"
    sed -n '1,120p' "$facts_path" || true
    echo "--------------------------------------------------------------------------------"

    echo "[REQUEST] (first 120 lines)"
    sed -n '1,120p' "$request_path" || true
    echo "--------------------------------------------------------------------------------"

    echo "Next action:"
    echo "  1) codex にこう依頼："
    echo "     「$request_path を読んで、テンプレ厳守でMarkdownのみ出力」"
    echo "  2) 出力をこの後に開く editor で $output_path に貼り付けて保存"
    echo ""

    # continue/skip/quit
    if [ -n "$TTY_IN" ]; then
      # read を /dev/tty から取る（stdinが壊れても対話できる）
      choice=""
      while true; do
        read -r -p "Proceed? [Enter=continue / s=skip / q=quit] " choice < "$TTY_IN" || true
        case "${choice:-}" in
          "" ) break ;;
          s|S ) echo "SKIP: user skipped"; continue 2 ;;
          q|Q ) echo "QUIT."; exit 0 ;;
          * ) echo "Input error. Use Enter / s / q." ;;
        esac
      done
    else
      # fallback: stdin
      if ! prompt_choice "Proceed?"; then
        true
      fi
      rc=$?
      if [ $rc -eq 2 ]; then
        echo "SKIP: user skipped"
        continue
      elif [ $rc -eq 3 ]; then
        echo "QUIT."
        exit 0
      fi
    fi

    # Ensure output file exists and open editor
    ensure_output_skeleton "$output_path"
    echo ""
    echo "Opening editor: $output_path"
    echo "（ここに codex の出力Markdownを貼って保存し、閉じてください）"
    "$EDITOR_CMD" "$output_path"

    # validate
    if ! validate_output "$output_path"; then
      if [ -n "$TTY_IN" ]; then
        read -r -p "Validation failed. Continue anyway? [Enter=yes / q=quit] " v < "$TTY_IN" || true
        if [ "${v:-}" = "q" ] || [ "${v:-}" = "Q" ]; then
          echo "QUIT."
          exit 0
        fi
      else
        read -r -p "Validation failed. Continue anyway? [Enter=yes / q=quit] " v || true
        if [ "${v:-}" = "q" ] || [ "${v:-}" = "Q" ]; then
          echo "QUIT."
          exit 0
        fi
      fi
    fi

    # upsert
    if [ -z "${issue_url:-}" ]; then
      echo "SKIP: issue_url is empty (cannot upsert)"
      continue
    fi

    scripts/upsert_issue_comment.sh "$issue_url" "$output_path"
  done
} < "$RUNLIST"

echo ""
echo "DONE."
