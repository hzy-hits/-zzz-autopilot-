"""Tests for the execution plan system."""

from pathlib import Path
import tempfile

from zzz_agent.planning.store import PlanStore, PlanStatus, StepStatus


def test_create_plan():
    with tempfile.TemporaryDirectory() as tmp:
        store = PlanStore(Path(tmp) / "plans")
        plan = store.create_plan(
            goal="Level Lina to 60",
            steps=[
                {"app_id": "coffee", "expected_outcome": "stamina +60"},
                {"app_id": "hollow_zero", "config": {"floor": 3}, "precondition": "stamina >= 60"},
            ],
        )
        assert plan.goal == "Level Lina to 60"
        assert len(plan.steps) == 2
        assert plan.steps[0].app_id == "coffee"
        assert plan.steps[1].config == {"floor": 3}
        assert plan.status == PlanStatus.ACTIVE


def test_update_step():
    with tempfile.TemporaryDirectory() as tmp:
        store = PlanStore(Path(tmp) / "plans")
        plan = store.create_plan(goal="Test", steps=[{"app_id": "coffee"}, {"app_id": "scratch_card"}])
        updated = store.update_step("step_1", "completed", notes="Done")
        assert updated.steps[0].status == StepStatus.COMPLETED
        assert updated.steps[0].notes == "Done"
        assert updated.current_step.id == "step_2"


def test_plan_auto_complete():
    with tempfile.TemporaryDirectory() as tmp:
        store = PlanStore(Path(tmp) / "plans")
        store.create_plan(goal="Test", steps=[{"app_id": "a"}, {"app_id": "b"}])
        store.update_step("step_1", "completed")
        plan = store.update_step("step_2", "completed")
        assert plan.status == PlanStatus.COMPLETED


def test_cancel_existing_on_new_plan():
    with tempfile.TemporaryDirectory() as tmp:
        store = PlanStore(Path(tmp) / "plans")
        plan1 = store.create_plan(goal="Plan 1", steps=[{"app_id": "a"}])
        plan2 = store.create_plan(goal="Plan 2", steps=[{"app_id": "b"}])
        assert store.get_active_plan().id == plan2.id
        # Reload to verify plan1 was cancelled on disk
        plans = store.list_plans()
        cancelled = [p for p in plans if p.id == plan1.id]
        assert len(cancelled) == 1
        assert cancelled[0].status == PlanStatus.CANCELLED


def test_persistence():
    with tempfile.TemporaryDirectory() as tmp:
        plans_dir = Path(tmp) / "plans"
        store1 = PlanStore(plans_dir)
        store1.create_plan(goal="Persist", steps=[{"app_id": "coffee"}])
        store1.update_step("step_1", "in_progress")

        # Reload
        store2 = PlanStore(plans_dir)
        plan = store2.get_active_plan()
        assert plan is not None
        assert plan.goal == "Persist"
        assert plan.steps[0].status == StepStatus.IN_PROGRESS


def test_progress_summary():
    with tempfile.TemporaryDirectory() as tmp:
        store = PlanStore(Path(tmp) / "plans")
        store.create_plan(goal="Test", steps=[{"app_id": "a"}, {"app_id": "b"}, {"app_id": "c"}])
        store.update_step("step_1", "completed")
        plan = store.get_active_plan()
        assert plan.progress_summary == "1/3 steps completed"
