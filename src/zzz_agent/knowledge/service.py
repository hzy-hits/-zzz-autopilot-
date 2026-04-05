"""Three-layer game knowledge service.

Query priority: Framework built-in > Remote synced > Agent-discovered.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from zzz_agent.knowledge.rag import RAGIndex


@dataclass
class KnowledgeResult:
    """Result from a knowledge query."""

    found: bool
    source: str
    data: dict | list | str
    confidence: str


class KnowledgeService:
    """Three-layer knowledge query and management."""

    def __init__(self, config_dir: Path, framework_config_dir: Path | None = None) -> None:
        self._config_dir = config_dir
        self._framework_config_dir = framework_config_dir
        self._knowledge_dir = config_dir / "game_knowledge" / "core"
        self._discovered_dir = config_dir / "discovered_knowledge"
        self._guides_dir = config_dir / "game_knowledge" / "guides"
        self._rag_index = RAGIndex(self._guides_dir, self._guides_dir / ".index")

        self._discovered_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, dict] = {}
        self._load_all()

    def _load_all(self) -> None:
        self._cache.clear()
        if not self._knowledge_dir.exists():
            return

        for yml_file in self._knowledge_dir.glob("*.yml"):
            try:
                with yml_file.open(encoding="utf-8") as f:
                    self._cache[yml_file.stem] = yaml.safe_load(f) or {}
            except Exception:
                continue

    def query(self, question: str) -> KnowledgeResult:
        question_lower = question.lower()

        if self._framework_config_dir and self._framework_config_dir.exists():
            framework_result = self._search_framework(question_lower)
            if framework_result is not None:
                return KnowledgeResult(True, "framework", framework_result, "authoritative")

        for _file_key, data in self._cache.items():
            result = self._search_any(data, question_lower)
            if result is not None:
                return KnowledgeResult(True, "remote", result, "synced")

        discovered_result = self._search_discovered(question_lower)
        if discovered_result is not None:
            return KnowledgeResult(True, "discovered", discovered_result, "unverified")

        return KnowledgeResult(False, "none", "No knowledge found for this query.", "none")

    def update_discovered(self, key: str, value: str) -> bool:
        # Sanitize key to prevent path traversal
        safe_key = key.replace("/", "_").replace("\\", "_").replace("..", "_").strip(".")
        if not safe_key:
            return False
        file_path = self._discovered_dir / f"{safe_key}.yml"
        entry = {"key": key, "value": value, "verified": False, "source": "agent_discovered"}
        with file_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(entry, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return True

    def sync_remote(self) -> dict:
        config_path = self._config_dir / "game_knowledge" / "knowledge_config.yml"
        if not config_path.exists():
            return {"status": "failed", "reason": f"knowledge config missing: {config_path}"}

        try:
            with config_path.open(encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}
        except Exception as exc:
            return {"status": "failed", "reason": f"failed to read knowledge config: {exc}"}

        remote_source = self._find_remote_source(config_data)
        if remote_source is None:
            return {"status": "not_configured", "reason": "no remote source configured"}

        url = str(remote_source.get("url") or "").strip()
        if not url:
            return {"status": "not_configured", "reason": "remote url is empty"}

        if url.startswith("file://"):
            result = self._sync_from_local(Path(url[7:]))
            self.reload()
            return result

        if url.startswith("http://") or url.startswith("https://") or url.endswith(".git"):
            result = self._sync_from_git(url)
            self.reload()
            return result

        return {"status": "failed", "reason": f"unsupported remote scheme: {url}"}

    def reload(self) -> None:
        self._load_all()

    def list_knowledge_files(self) -> list[str]:
        return list(self._cache.keys())

    def get_knowledge_file(self, name: str) -> dict | None:
        return self._cache.get(name)

    def search_guides(self, query: str, top_k: int = 3) -> list[dict[str, object]]:
        if not self._rag_index.is_indexed():
            self._rag_index.build_index()
        return [excerpt.__dict__ for excerpt in self._rag_index.search(query=query, top_k=top_k)]

    def _find_remote_source(self, config_data: dict) -> dict | None:
        sources = config_data.get("knowledge_sources")
        if not isinstance(sources, list):
            return None
        for source in sources:
            if isinstance(source, dict) and source.get("type") == "remote":
                return source
        return None

    def _sync_from_local(self, source_path: Path) -> dict:
        if not source_path.exists():
            return {"status": "failed", "reason": f"source path not found: {source_path}"}
        if not source_path.is_dir():
            return {"status": "failed", "reason": f"source path is not a directory: {source_path}"}
        if source_path.resolve() == self._knowledge_dir.resolve():
            return {"status": "success", "updated_files": []}

        self._knowledge_dir.mkdir(parents=True, exist_ok=True)
        updated: list[str] = []
        for src in source_path.rglob("*"):
            if not src.is_file() or src.suffix.lower() not in {".yml", ".yaml", ".json"}:
                continue
            relative = src.relative_to(source_path)
            dst = self._knowledge_dir / relative
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            updated.append(str(relative))
        return {"status": "success", "updated_files": updated}

    def _sync_from_git(self, url: str) -> dict:
        self._knowledge_dir.mkdir(parents=True, exist_ok=True)
        try:
            completed = subprocess.run(
                ["git", "clone", "--depth", "1", "--", url, str(self._knowledge_dir)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return {"status": "failed", "reason": "git is not available"}
        if completed.returncode not in {0, 128}:
            return {"status": "failed", "reason": f"git clone failed with code {completed.returncode}"}
        return {"status": "success", "updated_files": []}

    def _search_any(self, data: dict | list | str, query: str) -> dict | list | str | None:
        if isinstance(data, dict):
            return self._search_dict(data, query)
        if isinstance(data, list):
            return self._search_list(data, query)
        return data if query in str(data).lower() else None

    def _search_dict(self, data: dict, query: str) -> dict | list | str | None:
        for key, value in data.items():
            if query in str(key).lower():
                return {key: value}
            if isinstance(value, dict):
                result = self._search_dict(value, query)
                if result is not None:
                    return result
            elif isinstance(value, list):
                result = self._search_list(value, query)
                if result is not None:
                    return result
            elif query in str(value).lower():
                return {key: value}
        return None

    def _search_list(self, data: list, query: str) -> dict | list | str | None:
        matches: list = []
        for item in data:
            if isinstance(item, dict):
                result = self._search_dict(item, query)
                if result is not None:
                    matches.append(result)
            elif isinstance(item, list):
                result = self._search_list(item, query)
                if result is not None:
                    matches.append(result)
            elif query in str(item).lower():
                matches.append(item)
        return matches or None

    def _search_framework(self, query: str) -> dict | list | str | None:
        if self._framework_config_dir is None or not self._framework_config_dir.exists():
            return None

        for config_file in self._framework_config_dir.rglob("*"):
            if config_file.is_dir():
                continue
            suffix = config_file.suffix.lower()
            if suffix in {".yml", ".yaml"}:
                try:
                    with config_file.open(encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                except Exception:
                    continue
            elif suffix == ".json":
                try:
                    with config_file.open(encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    continue
            else:
                continue

            result = self._search_any(data, query)
            if result is not None:
                return result
        return None

    def _search_discovered(self, query: str) -> dict | None:
        if not self._discovered_dir.exists():
            return None
        for yml_file in self._discovered_dir.glob("*.yml"):
            try:
                with yml_file.open(encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception:
                continue
            if query in str(data).lower():
                return data
        return None
