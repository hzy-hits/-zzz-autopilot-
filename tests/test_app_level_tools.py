"""Tests for app-level orchestration helpers."""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

import yaml

from zzz_agent.tools.analysis import _app_log_tokens, _parse_log_lines
from zzz_agent.tools.perception import _extra_run_record_fields
from zzz_agent.tools.perception import _run_count_today as perception_run_count_today
from zzz_agent.tools.planning import _load_daily_task_descriptions
from zzz_agent.tools.planning import _run_count_today as planning_run_count_today


def test_load_daily_task_descriptions_reads_config() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        core_dir = config_dir / "game_knowledge" / "core"
        core_dir.mkdir(parents=True, exist_ok=True)
        (core_dir / "daily_tasks.yml").write_text(
            yaml.safe_dump(
                {
                    "daily_tasks": [
                        {"app_id": "email", "description": "Claim mail rewards"},
                        {"app_id": "coffee", "description": "Claim coffee stamina"},
                    ]
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        descriptions = _load_daily_task_descriptions(config_dir)

        assert descriptions == {
            "email": "Claim mail rewards",
            "coffee": "Claim coffee stamina",
        }


def test_run_count_helpers_prefer_run_record_counters() -> None:
    record = SimpleNamespace(daily_run_times=3, run_times=7)

    assert planning_run_count_today(record, "completed") == 3
    assert perception_run_count_today(record, "completed") == 3


def test_run_count_helpers_fallback_to_status_when_counters_missing() -> None:
    record = SimpleNamespace()

    assert planning_run_count_today(record, "completed") == 1
    assert perception_run_count_today(record, "not_run") == 0


def test_extra_run_record_fields_collects_optional_progress() -> None:
    record = SimpleNamespace(daily_run_times=2, weekly_run_times=5, left_times=1, run_times=8)

    assert _extra_run_record_fields(record) == {
        "daily_run_times": 2,
        "weekly_run_times": 5,
        "left_times": 1,
        "run_times": 8,
    }


def test_parse_log_lines_matches_app_name_alias() -> None:
    text = "\n".join(
        [
            "[2026-04-06 10:00:00] [email_app.py 12] [INFO]: starting Email",
            "[2026-04-06 10:00:01] [email_app.py 15] [ERROR]: Email failed to open mailbox",
            "[2026-04-06 10:00:02] [coffee_app.py 9] [INFO]: unrelated Coffee message",
        ]
    )

    entries = _parse_log_lines(text, ["email", "Email"])

    assert len(entries) == 2
    assert entries[-1]["level"] == "ERROR"
    assert "mailbox" in entries[-1]["message"]


def test_app_log_tokens_include_app_name_when_available() -> None:
    run_context = SimpleNamespace(get_application_name=lambda app_id: "Email" if app_id == "email" else app_id)
    ctx = SimpleNamespace(z_ctx=SimpleNamespace(run_context=run_context))

    assert _app_log_tokens(ctx, "email") == ["email", "Email"]
