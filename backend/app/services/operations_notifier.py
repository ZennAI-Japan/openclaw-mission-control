"""Discord notifier integration skeleton for operations summary reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import settings

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class DeliveryResult:
    """Outcome returned by a notifier delivery adapter."""

    accepted: bool
    reason: str | None = None


class SummaryDeliveryAdapter(Protocol):
    """Boundary for summary delivery implementations."""

    def deliver_summary(self, *, channel: str, payload: dict[str, object]) -> DeliveryResult:
        """Attempt to deliver a summary notification."""


@dataclass(slots=True)
class LoggingSummaryDeliveryAdapter:
    """Safe default adapter that records intent without external delivery."""

    def deliver_summary(self, *, channel: str, payload: dict[str, object]) -> DeliveryResult:
        logger.info(
            "operations.discord.summary.pending_delivery",
            extra={"channel": channel, "payload": payload},
        )
        return DeliveryResult(accepted=False, reason="delivery_adapter_not_implemented")


@dataclass(slots=True)
class DiscordSummaryNotifier:
    """Send periodic runtime summary notifications.

    This skeleton intentionally logs payloads only; wiring to the Discord delivery
    client should happen in a follow-up PR.
    """

    channel: str | None = None
    enabled: bool = False
    delivery_adapter: SummaryDeliveryAdapter = field(default_factory=LoggingSummaryDeliveryAdapter)

    def notify_summary(self, payload: dict[str, object]) -> bool:
        if not self.enabled:
            logger.debug("operations.discord.summary.skipped", extra={"reason": "disabled"})
            return False
        if not self.channel:
            logger.debug("operations.discord.summary.skipped", extra={"reason": "missing_channel"})
            return False
        result = self.delivery_adapter.deliver_summary(channel=self.channel, payload=payload)
        if not result.accepted:
            logger.info(
                "operations.discord.summary.not_delivered",
                extra={"channel": self.channel, "reason": result.reason},
            )
        return result.accepted


def build_discord_summary_notifier() -> DiscordSummaryNotifier:
    """Build a config-driven notifier with a safe default adapter."""

    channel = settings.operations_notifier_channel.strip() or None
    return DiscordSummaryNotifier(
        channel=channel,
        enabled=bool(settings.operations_notifier_enabled and channel),
    )
