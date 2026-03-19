# FIFO Watchdog 運用

FIFO基盤（`projects/openclaw-fifo-job-system`）の異常を検知し、GitHub Issueを自動起票する運用。

## 何を検知するか

- 必須サービス不足: `redis`, `worker`, `scheduler`, `queue-sync`
- stale processing: SQLiteの `processing` タスクがしきい値（既定30分）以上更新されない

## 実行コマンド

```bash
cd openclaw-mission-control
scripts/fifo_watchdog.sh
```

## 環境変数

- `REPO` (default: `ZennAI-Japan/openclaw-mission-control`)
- `FIFO_PROJECT_DIR` (default: `~/.openclaw/workspace/projects/openclaw-fifo-job-system`)
- `DASHBOARD_FILE` (default: `~/.openclaw/workspace/FIFO_QUEUE.md`)
- `STALE_MINUTES` (default: `30`)

## 重複起票防止

Issueタイトルに fingerprint を含め、同一 fingerprint の open issue がある場合は新規起票しない。

形式:

```text
fifo-watchdog|missing=<services>|stale=<task_ids>
```

## 期待動作

- 正常時: `fifo_watchdog: healthy` を出力し終了コード 0
- 異常時: bug ラベル付き Issue を自動作成
- 同一異常で既存Issueあり: `existing issue #...` を出力し終了コード 0
