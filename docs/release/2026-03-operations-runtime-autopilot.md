# Release note: Operations runtime API + Mission Control skill (2026-03)

## Summary
This release adds an initial Operations runtime control surface and a dashboard summary hook for Mission Control Autopilot workflows.

## What's included

### 1) Operations API guardrails
- All `/api/v1/operations/*` endpoints require admin auth.
- Global feature flag: `operations_api_enabled`.
- Write-route flag: `operations_runtime_write_enabled` for:
  - `POST /api/v1/operations/goals/generate`
  - `POST /api/v1/operations/dispatch/tick`

### 2) Runtime observability endpoints
- `GET /api/v1/operations/workers`
- `GET /api/v1/operations/tasks`
- `GET /api/v1/operations/events?limit=...`
- `GET /api/v1/operations/uptime`
- `GET /api/v1/operations/stalls`
- `GET /api/v1/operations/dashboard/summary`

`uptime` and `stalls` now expose worker utilization, queue depth by priority, stalled task ids, and project-level stall counts.

### 3) Safe notifier boundary
- `DiscordSummaryNotifier` now uses an adapter boundary (`SummaryDeliveryAdapter`).
- Default adapter is logging-only (no external delivery side effects).
- External delivery is enabled only when both are set:
  - `operations_notifier_enabled=true`
  - `operations_notifier_channel` is non-empty

## How to use with the Mission Control skill
Skill: `mission-control-autopilot`

Typical operator loop:
1. Enable API access in backend config (`operations_api_enabled=true`).
2. Optionally enable write routes for controlled dispatch (`operations_runtime_write_enabled=true`).
3. Observe runtime health via `/operations/uptime`, `/operations/stalls`, or `/operations/dashboard/summary`.
4. Trigger dispatch ticks and goal-driven task generation only when write flag is enabled.
5. Keep notifier in safe mode by default; wire an external adapter in a follow-up integration.

## Backward compatibility
- Default behavior remains safe-by-default: operations API and write paths can remain disabled by config.
- No database migration required for this increment.
