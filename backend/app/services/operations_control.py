"""Shared operations runtime state and helpers for API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.operations_autopilot import GoalTaskGenerator
from app.services.operations_dispatcher import DispatcherLoop
from app.services.operations_notifier import DiscordSummaryNotifier
from app.services.operations_runtime import InMemoryOperationsStore, QueueRefillPolicy

RUNTIME_STARTED_AT = datetime.now(UTC)
RUNTIME_STORE = InMemoryOperationsStore()
GOAL_GENERATOR = GoalTaskGenerator()
DISCORD_NOTIFIER = DiscordSummaryNotifier()

DISPATCHER_LOOP = DispatcherLoop(
    max_concurrency=3,
    refill_policy=QueueRefillPolicy(low_watermark=10, refill_batch_size=20, max_project_share=0.6),
)
STALL_THRESHOLD = timedelta(minutes=15)
