"""Tests for the knowledge service."""

import tempfile
from pathlib import Path

import yaml

from zzz_agent.knowledge.service import KnowledgeService


def _create_test_knowledge(config_dir: Path) -> None:
    """Create minimal test knowledge files."""
    core_dir = config_dir / "game_knowledge" / "core"
    core_dir.mkdir(parents=True, exist_ok=True)

    stamina_data = {
        "stamina": {
            "max": 240,
            "recovery_rate": "1 per 6 minutes",
        }
    }
    with open(core_dir / "stamina.yml", "w") as f:
        yaml.dump(stamina_data, f)

    chars_data = {
        "characters": [
            {"name": "Lina", "element": "Ether", "level_up_materials": [{"name": "Ether Core"}]},
            {"name": "Anby", "element": "Electric"},
        ]
    }
    with open(core_dir / "characters.yml", "w") as f:
        yaml.dump(chars_data, f)


def test_query_stamina():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        _create_test_knowledge(config_dir)
        svc = KnowledgeService(config_dir)
        result = svc.query("stamina")
        assert result.found is True
        assert "stamina" in str(result.data).lower()


def test_query_character():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        _create_test_knowledge(config_dir)
        svc = KnowledgeService(config_dir)
        result = svc.query("Lina")
        assert result.found is True
        assert "Lina" in str(result.data)


def test_query_not_found():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        _create_test_knowledge(config_dir)
        svc = KnowledgeService(config_dir)
        result = svc.query("xyznonexistent")
        assert result.found is False


def test_update_discovered():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        _create_test_knowledge(config_dir)
        svc = KnowledgeService(config_dir)
        success = svc.update_discovered("test_key", "test_value")
        assert success is True
        # Verify file exists
        assert (config_dir / "discovered_knowledge" / "test_key.yml").exists()
        # Query should find it
        result = svc.query("test_value")
        assert result.found is True
        assert result.confidence == "unverified"


def test_list_knowledge_files():
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        _create_test_knowledge(config_dir)
        svc = KnowledgeService(config_dir)
        files = svc.list_knowledge_files()
        assert "stamina" in files
        assert "characters" in files


def test_sync_from_git_uses_argument_separator(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        _create_test_knowledge(config_dir)
        cfg_dir = config_dir / "game_knowledge"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        config_file = cfg_dir / "knowledge_config.yml"
        config_file.write_text(
            """
knowledge_sources:
  - type: "remote"
    url: "https://example.com/knowledge.git"
""".strip(),
            encoding="utf-8",
        )

        calls: dict[str, list[str]] = {}

        class FakeResult:
            returncode = 0

        def fake_run(args, check, stdout, stderr):
            calls["args"] = args
            return FakeResult()

        monkeypatch.setattr("zzz_agent.knowledge.service.subprocess.run", fake_run)
        svc = KnowledgeService(config_dir)
        result = svc.sync_remote()
        assert result["status"] == "success"
        assert calls["args"][0:4] == ["git", "clone", "--depth", "1"]
        assert calls["args"][4] == "--"
        assert calls["args"][5] == "https://example.com/knowledge.git"
