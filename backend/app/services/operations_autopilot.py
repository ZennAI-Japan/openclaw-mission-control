"""Autonomous task generation for operations runtime."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.operations_runtime import Task


@dataclass(slots=True)
class GoalTaskGenerator:
    """Generate queue-ready tasks from high-level goals with duplicate suppression."""

    project: str = "mission-control"

    def generate(self, *, goal: str, max_tasks: int = 5) -> list[Task]:
        fragments = [part.strip() for part in re.split(r"[\n\.;。]+", goal) if part.strip()]
        if not fragments:
            fragments = [goal.strip()] if goal.strip() else []

        tasks: list[Task] = []
        seen_titles: set[str] = set()

        for index, fragment in enumerate(fragments[: max(0, max_tasks)]):
            normalized = " ".join(fragment.split())
            if not normalized:
                continue
            title = normalized[:80]
            dedupe_key = title.casefold()
            if dedupe_key in seen_titles:
                continue
            seen_titles.add(dedupe_key)
            priority = "P0" if index == 0 else ("P1" if index < 3 else "P2")
            task_id = self._task_id(goal=goal, index=index, title=title)
            tasks.append(
                Task(
                    id=task_id,
                    project=self.project,
                    title=title,
                    objective=goal,
                    priority=priority,
                )
            )
        return tasks

    def _task_id(self, *, goal: str, index: int, title: str) -> str:
        goal_token = re.sub(r"[^a-z0-9]+", "-", goal.casefold()).strip("-") or "goal"
        title_token = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-") or "task"
        return f"goal-{goal_token[:24]}-{index + 1}-{title_token[:24]}"
