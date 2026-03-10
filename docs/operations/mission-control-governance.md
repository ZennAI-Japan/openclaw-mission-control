# Mission Control Cross-Thread Governance

This operating model standardizes how work is continuously ingested, prioritized, dispatched, and reviewed across active Mission Control threads.

## 1) Intake policy

### Intake channels (ordered)
1. Production incidents / blocker reports
2. Merged PR follow-up tasks and known technical debt
3. Roadmap epics and strategic initiatives
4. Ad-hoc operator requests

### Intake rules
- Every task must map to one issue (or be created as a new issue before dispatch).
- Required metadata: `project`, `owner`, `priority`, `expected-outcome`, `due-window`, `dependencies`.
- Duplicate detection is mandatory before enqueue.
- If a task has unclear acceptance criteria, move to `needs-clarification` and do not dispatch.

## 2) Prioritization model

### Priority classes
- **P0**: Production down, security risk, critical revenue/user impact.
- **P1**: High-value delivery with near-term deadlines.
- **P2**: Planned improvements and non-urgent quality work.

### Prioritization score
Use weighted score to break ties inside each priority:

`Score = (BusinessImpact x 0.4) + (Urgency x 0.25) + (RiskReduction x 0.2) + (ExecutionReadiness x 0.15)`

- Normalize each factor to 1–5.
- Re-score backlog daily before dispatch review.

## 3) Dispatch policy

### Capacity and concurrency
- Reserve at least 1 worker slot for P0/P1 interrupts.
- Dispatch queue order: P0 -> P1 -> P2, then by score and age.
- Avoid dispatching tasks with unresolved blockers or missing context.

### Thread assignment
- Prefer project affinity to reduce handoff overhead.
- Rotate high-cognitive-load work to prevent thread starvation.
- Auto-retry failed tasks with bounded exponential backoff (max 3 attempts).

### Escalation
Escalate immediately when:
- P0 remains unassigned for >10 minutes.
- Any task exceeds stall threshold (15 minutes) twice.
- Queue depth for P0/P1 exceeds available capacity for next 2 cycles.

## 4) SLA / SLO targets

| Metric | Target |
| --- | --- |
| P0 first dispatch latency | <= 10 minutes |
| P1 first dispatch latency | <= 60 minutes |
| P2 first dispatch latency | <= 24 hours |
| Mean stall recovery time | <= 20 minutes |
| Weekly dispatch success rate | >= 95% |
| Effective worker uptime | >= 99% |

## 5) Reporting cadence

### Daily (operations)
- **Time**: Start of day + end of day (JST)
- **Report**: queue depth by priority, dispatch count, blocked tasks, top incidents, SLA misses

### Weekly (leadership)
- **Time**: fixed weekly review window
- **Report**: throughput trend, backlog growth, SLA/SLO attainment, top recurring blockers, planned process improvements

### Monthly (governance)
- Policy tuning review for thresholds, scoring weights, and escalation guardrails.

## 6) Execution runbook rhythm

### Daily dispatch review (30 minutes)
1. Validate worker availability and queue health.
2. Re-score candidate tasks and confirm dependencies.
3. Dispatch top tasks and reserve interrupt slot.
4. Record decisions in timeline + issue updates.
5. Trigger escalation for any SLA risk.

### Weekly backlog grooming (60 minutes)
1. Audit new intake for duplicates and scope clarity.
2. Reclassify stale/blocked items.
3. Split oversized tasks into dispatchable units.
4. Promote next-week candidates to ready queue.
5. Archive done/cancelled work and publish backlog delta report.

## 7) Ownership model

- **Mission Control operator**: intake triage, dispatch execution, incident escalation.
- **Project owners**: acceptance criteria quality, dependency unblocking, outcome validation.
- **Leadership**: SLA governance, priority arbitration, and capacity adjustments.
