Stacked on top of #6. Link: #5

## Scope
- Add `/api/v1/operations/dashboard/summary` read-only integration endpoint for dashboard consumption.
- Reuse existing uptime/stall worker/queue aggregations to avoid duplicate frontend composition.
- Add API assertions for the new dashboard summary payload.

## Checklist
- [x] API hook for dashboard integration
- [x] Test coverage for payload contract
- [ ] Frontend wiring to consume summary endpoint (next increment)
