# ruff: noqa: INP001

from __future__ import annotations

import pytest

from app.core.config import settings
from app.services import operations_notifier
from app.services.operations_notifier import DeliveryResult


def test_notifier_builder_requires_flag_and_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "operations_notifier_enabled", False)
    monkeypatch.setattr(settings, "operations_notifier_channel", "ops-runtime")
    notifier = operations_notifier.build_discord_summary_notifier()
    assert notifier.enabled is False

    monkeypatch.setattr(settings, "operations_notifier_enabled", True)
    monkeypatch.setattr(settings, "operations_notifier_channel", "")
    notifier = operations_notifier.build_discord_summary_notifier()
    assert notifier.enabled is False


def test_notifier_uses_adapter_boundary_when_enabled() -> None:
    deliveries: list[tuple[str, dict[str, object]]] = []

    class _Adapter:
        def deliver_summary(self, *, channel: str, payload: dict[str, object]) -> DeliveryResult:
            deliveries.append((channel, payload))
            return DeliveryResult(accepted=True)

    notifier = operations_notifier.DiscordSummaryNotifier(
        channel="ops-runtime",
        enabled=True,
        delivery_adapter=_Adapter(),
    )

    delivered = notifier.notify_summary({"queue_size": 3})

    assert delivered is True
    assert deliveries == [("ops-runtime", {"queue_size": 3})]


def test_notifier_default_adapter_stays_safe() -> None:
    notifier = operations_notifier.DiscordSummaryNotifier(
        channel="ops-runtime",
        enabled=True,
    )

    delivered = notifier.notify_summary({"queue_size": 3})

    assert delivered is False
