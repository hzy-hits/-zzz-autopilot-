"""Three-layer game knowledge service.

Query priority: Framework built-in > Remote synced > Agent-discovered.

Layer 1 (Framework): Original project's config/ — app configs, screen routes, character templates.
    Updated when the framework is git-pulled. Read-only from Agent's perspective.

Layer 2 (Remote): Periodically synced game data — characters, materials, dungeon mechanics.
    Stored in config/game_knowledge/core/*.yml. Updated via sync_remote().

Layer 3 (Agent-discovered): Knowledge the Agent writes during gameplay.
    Stored in config/discovered_knowledge/*.yml. Tagged as unverified.
    Yields to Layer 1 and Layer 2 on conflict.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class KnowledgeResult:
    """Result from a knowledge query."""

    found: bool
    source: str  # "framework" | "remote" | "discovered" | "none"
    data: dict | list | str
    confidence: str  # "authoritative" | "synced" | "unverified"


class KnowledgeService:
    """Three-layer knowledge query and management.

    Args:
        config_dir: Path to zzz-agent's config/ directory.
        framework_config_dir: Path to the original framework's config/ directory (Layer 1).
    """

    def __init__(self, config_dir: Path, framework_config_dir: Path | None = None) -> None:
        self._config_dir = config_dir
        self._framework_config_dir = framework_config_dir
        self._knowledge_dir = config_dir / "game_knowledge" / "core"
        self._discovered_dir = config_dir / "discovered_knowledge"
        self._discovered_dir.mkdir(parents=True, exist_ok=True)

        self._cache: dict[str, dict] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load all YAML knowledge files into memory cache."""
        self._cache.clear()
        for yml_file in self._knowledge_dir.glob("*.yml"):
            with open(yml_file, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                self._cache[yml_file.stem] = data

    def query(self, question: str) -> KnowledgeResult:
        """Query game knowledge across all three layers.

        Searches structured data first (exact key/field match),
        then falls back to discovered knowledge.

        Args:
            question: Natural language question or keyword to search for.

        Returns:
            KnowledgeResult with source attribution and confidence level.
        """
        question_lower = question.lower()

        # Layer 1 + 2: Search structured YAML data (core knowledge)
        for _file_key, data in self._cache.items():
            result = self._search_dict(data, question_lower)
            if result is not None:
                return KnowledgeResult(found=True, source="remote", data=result, confidence="synced")

        # Layer 1: Search framework config if available
        if self._framework_config_dir and self._framework_config_dir.exists():
            framework_result = self._search_framework(question_lower)
            if framework_result is not None:
                return KnowledgeResult(
                    found=True, source="framework", data=framework_result, confidence="authoritative"
                )

        # Layer 3: Search agent-discovered knowledge
        discovered_result = self._search_discovered(question_lower)
        if discovered_result is not None:
            return KnowledgeResult(found=True, source="discovered", data=discovered_result, confidence="unverified")

        return KnowledgeResult(found=False, source="none", data="No knowledge found for this query.", confidence="none")

    def update_discovered(self, key: str, value: str) -> bool:
        """Write agent-discovered knowledge to disk.

        All discovered knowledge is tagged as unverified and yields
        to Layer 1/2 sources on conflict.

        Args:
            key: Knowledge key (used as filename stem).
            value: Knowledge content (free-form text or YAML string).

        Returns:
            True if written successfully.
        """
        file_path = self._discovered_dir / f"{key}.yml"
        entry = {"key": key, "value": value, "verified": False, "source": "agent_discovered"}
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(entry, f, allow_unicode=True, default_flow_style=False)
        return True

    def sync_remote(self) -> dict:
        """Pull latest knowledge from remote repository.

        TODO(codex): Implement remote sync logic.
        - Read remote URL from config/game_knowledge/knowledge_config.yml
        - Git clone/pull or HTTP fetch the remote knowledge repo
        - Merge into config/game_knowledge/core/
        - Reload cache

        Returns:
            Dict with sync results: {"updated_files": [...], "status": "success"|"failed"}
        """
        raise NotImplementedError("Remote knowledge sync not yet implemented")

    def reload(self) -> None:
        """Reload all knowledge from disk."""
        self._load_all()

    def list_knowledge_files(self) -> list[str]:
        """List all loaded knowledge file names."""
        return list(self._cache.keys())

    def get_knowledge_file(self, name: str) -> dict | None:
        """Get contents of a specific knowledge file."""
        return self._cache.get(name)

    def _search_dict(self, data: dict, query: str, path: str = "") -> dict | list | str | None:
        """Recursively search a dict for keys/values matching the query."""
        for key, value in data.items():
            key_str = str(key).lower()
            if query in key_str:
                return {key: value}
            if isinstance(value, dict):
                result = self._search_dict(value, query, f"{path}.{key}")
                if result is not None:
                    return result
            elif isinstance(value, list):
                matches = []
                for item in value:
                    if isinstance(item, dict):
                        for v in item.values():
                            if query in str(v).lower():
                                matches.append(item)
                                break
                    elif query in str(item).lower():
                        matches.append(item)
                if matches:
                    return matches
            elif query in str(value).lower():
                return {key: value}
        return None

    def _search_framework(self, query: str) -> dict | None:
        """Search the original framework's config directory.

        TODO(codex): Implement framework config search.
        - Search through framework_config_dir for app configs, screen definitions, etc.
        - Parse relevant YAML/JSON files
        - Return matching entries

        Returns:
            Matching data or None.
        """
        return None

    def _search_discovered(self, query: str) -> dict | None:
        """Search agent-discovered knowledge files."""
        for yml_file in self._discovered_dir.glob("*.yml"):
            with open(yml_file, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                if query in str(data).lower():
                    return data
        return None
