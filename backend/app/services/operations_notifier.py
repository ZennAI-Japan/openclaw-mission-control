"""Discord notifier integration skeleton for operations summary reporting."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class DiscordSummaryNotifier:
    """Send periodic runtime summary notifications.

    This skeleton intentionally logs payloads only; wiring to the Discord delivery
    client should happen in a follow-up PR.
    """

    channel: str | None = None
    enabled: bool = False

    def notify_summary(self, payload: dict[str, object]) -> bool:
        if not self.enabled:
            logger.debug("operations.discord.summary.skipped", extra={"reason": "disabled"})
            return False
        logger.info(
            "operations.discord.summary.pending_delivery",
            extra={"channel": self.channel, "payload": payload},
        )
        return True
