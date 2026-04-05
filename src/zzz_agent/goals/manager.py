"""Player goal management with YAML persistence.

Goals represent medium-to-long-term player objectives like:
  - "Level up Lina to 60"
  - "Complete all daily tasks"
  - "Reach S rank in Shiyu Defense"

Each goal can have sub-tasks and progress notes. Goals persist across
Agent sessions in config/goals.yml.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path

import yaml


class GoalStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    RECURRING = "recurring"


class GoalPriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Goal:
    id: str
    description: str
    priority: GoalPriority
    status: GoalStatus
    created: str
    sub_tasks: list[str] = field(default_factory=list)
    progress_notes: str = ""
    updated: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "created": self.created,
            "sub_tasks": self.sub_tasks,
            "progress_notes": self.progress_notes,
            "updated": self.updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Goal:
        return cls(
            id=data["id"],
            description=data["description"],
            priority=GoalPriority(data.get("priority", "medium")),
            status=GoalStatus(data.get("status", "pending")),
            created=data.get("created", ""),
            sub_tasks=data.get("sub_tasks", []),
            progress_notes=data.get("progress_notes", ""),
            updated=data.get("updated", ""),
        )


class GoalManager:
    """CRUD operations for player goals with YAML file persistence.

    Args:
        goals_file: Path to goals.yml for persistence.
    """

    def __init__(self, goals_file: Path) -> None:
        self._file = goals_file
        self._goals: dict[str, Goal] = {}
        self._load()

    def _load(self) -> None:
        """Load goals from YAML file."""
        if not self._file.exists():
            self._goals = {}
            return
        with open(self._file, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        self._goals = {}
        for goal_data in data.get("goals", []):
            goal = Goal.from_dict(goal_data)
            self._goals[goal.id] = goal

    def _save(self) -> None:
        """Persist goals to YAML file."""
        self._file.parent.mkdir(parents=True, exist_ok=True)
        data = {"goals": [g.to_dict() for g in self._goals.values()]}
        with open(self._file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    def list_goals(self) -> list[Goal]:
        """List all goals, ordered by priority (high first)."""
        priority_order = {GoalPriority.HIGH: 0, GoalPriority.MEDIUM: 1, GoalPriority.LOW: 2}
        return sorted(self._goals.values(), key=lambda g: priority_order.get(g.priority, 99))

    def get_goal(self, goal_id: str) -> Goal | None:
        """Get a specific goal by ID."""
        return self._goals.get(goal_id)

    def add_goal(self, description: str, priority: str = "medium", sub_tasks: list[str] | None = None) -> Goal:
        """Create a new goal.

        Args:
            description: What the player wants to achieve.
            priority: "high", "medium", or "low".
            sub_tasks: Optional list of sub-task descriptions.

        Returns:
            The created Goal.
        """
        goal = Goal(
            id=f"goal_{uuid.uuid4().hex[:8]}",
            description=description,
            priority=GoalPriority(priority),
            status=GoalStatus.PENDING,
            created=datetime.now().strftime("%Y-%m-%d"),
            sub_tasks=sub_tasks or [],
        )
        self._goals[goal.id] = goal
        self._save()
        return goal

    def update_goal(self, goal_id: str, status: str | None = None, progress_notes: str | None = None) -> Goal | None:
        """Update a goal's status or progress.

        Args:
            goal_id: Goal to update.
            status: New status (pending/in_progress/completed/abandoned/recurring).
            progress_notes: Free-form progress update text.

        Returns:
            Updated Goal, or None if not found.
        """
        goal = self._goals.get(goal_id)
        if goal is None:
            return None
        if status is not None:
            goal.status = GoalStatus(status)
        if progress_notes is not None:
            goal.progress_notes = progress_notes
        goal.updated = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._save()
        return goal

    def remove_goal(self, goal_id: str) -> bool:
        """Delete a goal.

        Returns:
            True if the goal existed and was removed.
        """
        if goal_id not in self._goals:
            return False
        del self._goals[goal_id]
        self._save()
        return True
