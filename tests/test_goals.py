"""Tests for the goal management system."""

import tempfile
from pathlib import Path

from zzz_agent.goals.manager import GoalManager, GoalPriority, GoalStatus


def test_add_and_list_goals():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = GoalManager(Path(tmp) / "goals.yml")
        mgr.add_goal("Level Lina to 60", "high")
        mgr.add_goal("Daily tasks", "medium")
        goals = mgr.list_goals()
        assert len(goals) == 2
        assert goals[0].priority == GoalPriority.HIGH
        assert goals[0].description == "Level Lina to 60"


def test_update_goal():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = GoalManager(Path(tmp) / "goals.yml")
        g = mgr.add_goal("Test goal", "low")
        updated = mgr.update_goal(g.id, status="completed", progress_notes="Done!")
        assert updated is not None
        assert updated.status == GoalStatus.COMPLETED
        assert updated.progress_notes == "Done!"


def test_remove_goal():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = GoalManager(Path(tmp) / "goals.yml")
        g = mgr.add_goal("To remove", "low")
        assert mgr.remove_goal(g.id) is True
        assert mgr.remove_goal("nonexistent") is False
        assert len(mgr.list_goals()) == 0


def test_persistence():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "goals.yml"
        mgr1 = GoalManager(path)
        mgr1.add_goal("Persist me", "high", sub_tasks=["Step 1", "Step 2"])

        # Reload from disk
        mgr2 = GoalManager(path)
        goals = mgr2.list_goals()
        assert len(goals) == 1
        assert goals[0].description == "Persist me"
        assert goals[0].sub_tasks == ["Step 1", "Step 2"]


def test_update_nonexistent():
    with tempfile.TemporaryDirectory() as tmp:
        mgr = GoalManager(Path(tmp) / "goals.yml")
        result = mgr.update_goal("fake_id", status="completed")
        assert result is None
