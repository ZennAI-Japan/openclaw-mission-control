# ruff: noqa: INP001

from __future__ import annotations

from app.services.operations_autopilot import GoalTaskGenerator


def test_goal_generator_splits_goal_and_assigns_priorities() -> None:
    generator = GoalTaskGenerator(project="growth")

    tasks = generator.generate(
        goal="Increase retention. improve onboarding; tune notifications", max_tasks=5
    )

    assert len(tasks) == 3
    assert [task.priority for task in tasks] == ["P0", "P1", "P1"]
    assert all(task.project == "growth" for task in tasks)


def test_goal_generator_deduplicates_fragments() -> None:
    generator = GoalTaskGenerator()

    tasks = generator.generate(goal="Ship API. Ship API。ship api", max_tasks=10)

    assert len(tasks) == 1
    assert tasks[0].title.lower() == "ship api"
