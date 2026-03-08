# OpenClaw Mission Control Operations Blueprint

## Objective
OpenClawのサブエージェント稼働を俯瞰し、停止時間を最小化する。

## Core Loops

### 1. Observability Loop (every 1 min)
- sessions/subagents status取得
- active/recent taskを正規化して保存
- 停滞時間(stall duration)を算出

### 2. Dispatcher Loop (every 30 sec)
- `maxConcurrency` に対する空きスロット計算
- queueから高優先度順にtaskをdispatch
- dispatch結果をtimelineに記録

### 3. Stocker Loop (every 5 min)
- queue件数が `lowWatermark` 未満なら自動補充
- project別のquotaを守る
- 重複タスクを検知し除外

### 4. Recovery Loop (every 2 min)
- stall threshold超過タスクを検知
- retry/backoff
- 上限到達時はescalation channelへ通知

## Data Model (minimum)

### Task
- `id`
- `project`
- `title`
- `objective`
- `priority` (P0/P1/P2)
- `status` (queued/running/blocked/done/failed)
- `attempt`
- `createdAt`
- `updatedAt`

### Worker
- `sessionKey`
- `agentId`
- `currentTaskId`
- `lastHeartbeatAt`
- `status`

### Event
- `timestamp`
- `type` (dispatch/retry/fail/recover/complete/refill)
- `taskId`
- `sessionKey`
- `payload`

## KPI
- Worker Utilization (%)
- Queue Health (count by priority)
- Stall Count / day
- Retry Success Rate
- Effective Uptime (%)

## Discord Reporting
- periodic summary: 10分間隔
- immediate alerts:
  - 全worker idle
  - stall連発
  - queue枯渇

## Initial Guardrails
- 最大同時実行数: 3
- stall threshold: 15分
- retry: 3回 (指数バックオフ)
- low watermark: 10 tasks
- refill batch: 20 tasks
