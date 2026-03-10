Part of operations runtime milestone delivery. Links: #1 #2 #3 #5

## ✅ Completed in this PR
- [x] (#1) Operations API auth/guardrails:
  - admin-auth dependency on `/api/v1/operations/*`
  - global API enable switch (`operations_api_enabled`)
  - write-route guardrail (`operations_runtime_write_enabled`) for `/goals/generate` and `/dispatch/tick`
- [x] (#2) Notifier boundary + config wiring:
  - adapter protocol (`SummaryDeliveryAdapter`)
  - safe logging adapter default (no external delivery side effects)
  - config-driven enablement requiring both enable flag and channel
- [x] (#3) Uptime/stall metrics enhancements:
  - worker totals/online/busy/idle/offline/utilization
  - queue depth and per-priority depth
  - stalled task ids, per-project counts, longest/average stall seconds
- [x] API + notifier tests for the above contracts

## ⏭ Remaining / follow-up
- [ ] (#5) Dashboard-facing integration hooks:
  - initial dashboard contract bridge for operations metrics
  - frontend wiring and smoke coverage in stacked follow-up PR

## Validation
- Targeted operations pytest suite: pass
- Ruff checks (touched files): pass
- Mypy checks (critical operations modules): pass
