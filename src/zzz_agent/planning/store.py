"""Execution plan persistence.

Plans decompose a high-level goal into sequential app dispatch steps.
They persist to disk so the Agent can resume after disconnection.

Example plan:
  goal: "Level up Lina to 60"
  steps:
    1. start_app("coffee") -> collect stamina
    2. start_app("hollow_zero", config={floor:3}) -> farm materials
    3. start_app("charge_plan", config={target:"exp"}) -> farm EXP
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path

import yaml


class StepStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PlanStep:
    id: str
    app_id: str
    config: dict = field(default_factory=dict)
    precondition: str | None = None
    expected_outcome: str = ""
    status: StepStatus = StepStatus.PENDING
    notes: str = ""
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "app_id": self.app_id,
            "config": self.config,
            "precondition": self.precondition,
            "expected_outcome": self.expected_outcome,
            "status": self.status.value,
            "notes": self.notes,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> PlanStep:
        return cls(
            id=data["id"],
            app_id=data["app_id"],
            config=data.get("config", {}),
            precondition=data.get("precondition"),
            expected_outcome=data.get("expected_outcome", ""),
            status=StepStatus(data.get("status", "pending")),
            notes=data.get("notes", ""),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at", ""),
        )


@dataclass
class ExecutionPlan:
    id: str
    goal: str
    steps: list[PlanStep]
    status: PlanStatus = PlanStatus.ACTIVE
    created: str = ""
    updated: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status.value,
            "created": self.created,
            "updated": self.updated,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict) -> ExecutionPlan:
        return cls(
            id=data["id"],
            goal=data["goal"],
            status=PlanStatus(data.get("status", "active")),
            created=data.get("created", ""),
            updated=data.get("updated", ""),
            steps=[PlanStep.from_dict(s) for s in data.get("steps", [])],
        )

    @property
    def current_step(self) -> PlanStep | None:
        """Get the first non-completed step."""
        for step in self.steps:
            if step.status in (StepStatus.PENDING, StepStatus.IN_PROGRESS):
                return step
        return None

    @property
    def progress_summary(self) -> str:
        done = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        total = len(self.steps)
        return f"{done}/{total} steps completed"


class PlanStore:
    """Execution plan persistence and query.

    Plans are stored as individual YAML files in plans_dir.
    Only one plan can be active at a time.

    Args:
        plans_dir: Directory to store plan YAML files.
    """

    def __init__(self, plans_dir: Path) -> None:
        self._dir = plans_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._active_plan: ExecutionPlan | None = None
        self._load_active()

    def _plan_file(self, plan_id: str) -> Path:
        return self._dir / f"{plan_id}.yml"

    def _load_active(self) -> None:
        """Find and load the active plan (if any)."""
        for yml_file in self._dir.glob("*.yml"):
            with open(yml_file, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if data.get("status") == "active":
                self._active_plan = ExecutionPlan.from_dict(data)
                return

    def _save_plan(self, plan: ExecutionPlan) -> None:
        plan.updated = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        with open(self._plan_file(plan.id), "w", encoding="utf-8") as f:
            yaml.dump(plan.to_dict(), f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    def get_active_plan(self) -> ExecutionPlan | None:
        """Get the currently active execution plan."""
        return self._active_plan

    def create_plan(self, goal: str, steps: list[dict]) -> ExecutionPlan:
        """Create a new execution plan, replacing any active plan.

        Args:
            goal: High-level goal description.
            steps: List of step dicts, each with keys:
                - app_id (str, required)
                - config (dict, optional)
                - precondition (str, optional)
                - expected_outcome (str, optional)

        Returns:
            The created ExecutionPlan.
        """
        if self._active_plan is not None:
            self._active_plan.status = PlanStatus.CANCELLED
            self._save_plan(self._active_plan)

        plan_id = f"plan_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
        plan_steps = []
        for i, step_data in enumerate(steps):
            plan_steps.append(
                PlanStep(
                    id=f"step_{i + 1}",
                    app_id=step_data["app_id"],
                    config=step_data.get("config", {}),
                    precondition=step_data.get("precondition"),
                    expected_outcome=step_data.get("expected_outcome", ""),
                )
            )

        plan = ExecutionPlan(
            id=plan_id,
            goal=goal,
            steps=plan_steps,
            created=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        )
        self._active_plan = plan
        self._save_plan(plan)
        return plan

    def update_step(self, step_id: str, status: str, notes: str = "") -> ExecutionPlan | None:
        """Update a step's status in the active plan.

        Args:
            step_id: Step to update (e.g. "step_1").
            status: New status (pending/in_progress/completed/failed/skipped).
            notes: Optional notes about the step result.

        Returns:
            Updated plan, or None if no active plan.
        """
        if self._active_plan is None:
            return None

        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        for step in self._active_plan.steps:
            if step.id == step_id:
                step.status = StepStatus(status)
                step.notes = notes
                if status == "in_progress":
                    step.started_at = now
                elif status in ("completed", "failed", "skipped"):
                    step.completed_at = now
                break

        # A failed step ends the plan immediately; later steps are no longer actionable.
        all_done = all(s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED) for s in self._active_plan.steps)
        any_failed = any(s.status == StepStatus.FAILED for s in self._active_plan.steps)
        if all_done:
            self._active_plan.status = PlanStatus.COMPLETED
        elif any_failed:
            self._active_plan.status = PlanStatus.FAILED

        self._save_plan(self._active_plan)
        return self._active_plan

    def list_plans(self, limit: int = 10) -> list[ExecutionPlan]:
        """List recent plans (most recent first)."""
        plans = []
        for yml_file in sorted(self._dir.glob("*.yml"), reverse=True):
            if len(plans) >= limit:
                break
            with open(yml_file, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            plans.append(ExecutionPlan.from_dict(data))
        return plans
