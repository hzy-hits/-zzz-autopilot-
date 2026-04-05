"""Screenshot -> structured game state extraction.

The extractor is best-effort and must not crash on OCR or framework issues.
It returns partial results alongside errors so higher layers can decide how
to proceed.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result from a state extraction attempt."""

    success: bool
    data: dict[str, Any]
    raw_ocr_text: str = ""
    errors: list[str] | None = None


class StateExtractor:
    """Extracts structured game state from screenshots."""

    _STAMINA_REGION = (1560, 30, 1880, 95)
    _ELEMENT_ALIASES: ClassVar[dict[str, tuple[str, ...]]] = {
        "Physical": ("physical", "物理"),
        "Fire": ("fire", "火"),
        "Ice": ("ice", "冰"),
        "Electric": ("electric", "electro", "电"),
        "Ether": ("ether", "以太"),
    }
    _WEAPON_TYPE_ALIASES: ClassVar[dict[str, tuple[str, ...]]] = {
        "Slash": ("slash", "斩击"),
        "Strike": ("strike", "打击"),
        "Pierce": ("pierce", "穿透"),
    }
    _SKILL_ALIASES: ClassVar[dict[str, tuple[str, ...]]] = {
        "basic_attack": ("basic attack", "normal attack", "普攻", "普通攻击"),
        "dodge": ("dodge", "闪避"),
        "assist": ("assist", "支援"),
        "special_attack": ("special attack", "special", "特殊技", "强化特殊技"),
        "chain_attack": ("chain attack", "chain", "连携技"),
        "ultimate": ("ultimate", "终结技", "终结"),
        "core_skill": ("core skill", "core", "核心技", "核心"),
    }
    _STAT_ALIASES: ClassVar[dict[str, tuple[str, ...]]] = {
        "HP": ("hp", "生命值"),
        "ATK": ("atk", "attack", "攻击力"),
        "DEF": ("def", "defense", "防御力"),
        "CRIT Rate": ("crit rate", "critical rate", "暴击率"),
        "CRIT DMG": ("crit dmg", "crit damage", "critical damage", "暴击伤害"),
        "PEN Ratio": ("pen ratio", "penetration ratio", "穿透率"),
        "PEN": ("pen", "penetration", "穿透值"),
        "Impact": ("impact", "冲击力"),
        "Anomaly Mastery": ("anomaly mastery", "异常掌控"),
        "Anomaly Proficiency": ("anomaly proficiency", "异常精通"),
        "Energy Regen": ("energy regen", "energy regeneration", "能量自动回复"),
    }
    _DESCRIPTOR_TOKENS: ClassVar[set[str]] = {
        "physical",
        "fire",
        "ice",
        "electric",
        "electro",
        "ether",
        "slash",
        "strike",
        "pierce",
        "物理",
        "火",
        "冰",
        "电",
        "以太",
        "斩击",
        "打击",
        "穿透",
        "rank",
        "级",
        "s",
        "a",
        "b",
    }

    def __init__(self, z_ctx: object) -> None:
        self._z_ctx = z_ctx

    def _safe_error(self, errors: list[str], context: str, exc: Exception) -> None:
        errors.append(f"{context}: {type(exc).__name__}: {exc}")
        logger.warning("%s failed: %s: %s", context, type(exc).__name__, exc)

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _record_ocr_failure(self, errors: list[str] | None, backend: str, exc: Exception) -> None:
        message = f"{backend}: {type(exc).__name__}: {exc}"
        logger.warning("OCR backend failed: %s", message)
        if errors is not None:
            errors.append(message)

    def _screenshot(self):
        ctx = self._z_ctx
        controller = getattr(ctx, "controller", None)
        if controller is None:
            raise RuntimeError("controller unavailable")
        _, image = controller.screenshot()
        if image is None:
            raise RuntimeError("screenshot unavailable")
        return image

    @staticmethod
    def _crop(image: Any, region: tuple[int, int, int, int]) -> Any:
        x1, y1, x2, y2 = region
        return image[y1:y2, x1:x2]

    def _ocr_text(
        self,
        image: Any,
        region: tuple[int, int, int, int] | None = None,
        *,
        errors: list[str] | None = None,
        context: str = "ocr",
    ) -> str:
        ctx = self._z_ctx
        if ctx is None:
            return ""

        ocr_service = getattr(ctx, "ocr_service", None)
        ocr = getattr(ctx, "ocr", None)
        if ocr_service is None and ocr is None:
            return ""

        target = self._crop(image, region) if region is not None else image

        try:
            if ocr_service is not None and hasattr(ocr_service, "get_ocr_result_list"):
                results = ocr_service.get_ocr_result_list(target)
                texts: list[str] = []
                for result in results:
                    data = getattr(result, "data", None)
                    if data:
                        texts.append(str(data))
                if texts:
                    return "\n".join(texts)
        except Exception as exc:
            self._record_ocr_failure(errors, f"{context}.ocr_service", exc)

        try:
            if ocr is not None and hasattr(ocr, "ocr"):
                results = ocr.ocr(target)
                texts: list[str] = []
                if isinstance(results, list):
                    for item in results:
                        data = getattr(item, "data", None)
                        if data:
                            texts.append(str(data))
                if texts:
                    return "\n".join(texts)
        except Exception as exc:
            self._record_ocr_failure(errors, f"{context}.ocr", exc)

        try:
            if ocr is not None and hasattr(ocr, "run_ocr_single_line"):
                return str(ocr.run_ocr_single_line(target) or "")
        except Exception as exc:
            self._record_ocr_failure(errors, f"{context}.run_ocr_single_line", exc)
            return ""

        return ""

    @staticmethod
    def _parse_stamina(text: str) -> tuple[int | None, int | None]:
        match = re.search(r"(\d{1,4})\s*/\s*(\d{1,4})", text.replace(",", ""))
        if match is None:
            return None, None
        return int(match.group(1)), int(match.group(2))

    @staticmethod
    def _parse_level(text: str) -> int | None:
        match = re.search(r"(?:Lv\.?|等级)\s*(\d{1,3})", text, re.IGNORECASE)
        if match is None:
            return None
        return int(match.group(1))

    @staticmethod
    def _parse_ascension(text: str) -> int | None:
        match = re.search(r"(?:Ascension|Asc|突破)\s*(?::|\uFF1A)?\s*(\d{1,2})", text, re.IGNORECASE)
        if match is None:
            return None
        return int(match.group(1))

    @staticmethod
    def _parse_name(line: str) -> str:
        clean = re.sub(r"\s+", " ", line).strip()
        if not clean:
            return ""
        if re.match(r"^(?:lv\.?|等级|ascension|asc|breakthrough|突破|slot|position|\+)", clean, re.IGNORECASE):
            return ""
        if re.match(
            r"^(?:hp|atk|attack|def|defense|crit|critical|pen|penetration|impact|anomaly|energy|"
            r"生命值|攻击力|防御力|暴击率|暴击伤害|穿透率|穿透值|冲击力|异常掌控|异常精通|能量自动回复)",
            clean,
            re.IGNORECASE,
        ):
            return ""
        split_pattern = (
            r"(?:\bLv\.?\b|等级|Ascension|Asc|Breakthrough|突破|"
            r"Basic(?: Attack)?|Dodge|Assist|Special(?: Attack)?|Chain(?: Attack)?|"
            r"Core(?: Skill)?|Ultimate|Slot|Position)"
        )
        candidate = re.split(split_pattern, clean, maxsplit=1, flags=re.IGNORECASE)[0].strip(" :-|")
        candidate = re.sub(r"^(?:[SABC]\s*[- ]?(?:rank|级)?\s+)", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\s+(?:[SABC]\s*[- ]?(?:rank|级)?)$", "", candidate, flags=re.IGNORECASE)
        if not candidate or candidate[0].isdigit():
            return ""
        tokens = [token.lower() for token in re.split(r"[\s/|,._-]+", candidate) if token]
        if tokens and all(token in StateExtractor._DESCRIPTOR_TOKENS for token in tokens):
            return ""
        return candidate

    @staticmethod
    def _parse_quantity(line: str) -> tuple[str, int] | None:
        clean = re.sub(r"\s+", " ", line).strip()
        match = re.search(r"(.+?)\s*(?:[x\u00d7*]\s*)?([0-9][0-9,]{0,8})$", clean)
        if match is None:
            return None
        name = match.group(1).strip()
        name = re.sub(r"^(?:[SABC]\s*[- ]?(?:rank|级)?\s+)", "", name, flags=re.IGNORECASE)
        return name, int(match.group(2).replace(",", ""))

    @classmethod
    def _find_alias(cls, text: str, alias_map: dict[str, tuple[str, ...]]) -> str | None:
        lowered = text.lower()
        for canonical, aliases in alias_map.items():
            if any(alias.lower() in lowered for alias in aliases):
                return canonical
        return None

    @staticmethod
    def _parse_rarity(text: str) -> str | None:
        clean = text.strip()
        star_count = clean.count("★") or clean.count("⭐")
        if star_count:
            return f"{star_count}-star"

        patterns = (
            r"(?:rarity|rank|grade|品质|稀有度)\s*(?::|\uFF1A)?\s*([SABC])",
            r"\b([SABC])\s*[- ]?rank\b",
            r"([SABC])级",
            r"\b([SABC])\b",
        )
        for pattern in patterns:
            match = re.search(pattern, clean, re.IGNORECASE)
            if match is not None:
                return match.group(1).upper()
        return None

    @classmethod
    def _parse_element(cls, text: str) -> str | None:
        return cls._find_alias(text, cls._ELEMENT_ALIASES)

    @classmethod
    def _parse_weapon_type(cls, text: str) -> str | None:
        return cls._find_alias(text, cls._WEAPON_TYPE_ALIASES)

    @staticmethod
    def _parse_position(text: str) -> int | None:
        match = re.search(r"(?:slot|position)\s*(?::|\uFF1A|#)?\s*([1-6])", text, re.IGNORECASE)
        if match is not None:
            return int(match.group(1))

        match = re.search(r"([1-6])\s*号位", text)
        if match is not None:
            return int(match.group(1))

        chinese_match = re.search(r"([一二三四五六])\s*号位", text)
        if chinese_match is None:
            return None

        return {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6}[chinese_match.group(1)]

    @staticmethod
    def _parse_enhancement_level(text: str) -> int | None:
        match = re.search(r"(?:\+|Lv\.?\s*|等级\s*)(\d{1,2})", text, re.IGNORECASE)
        if match is None:
            return None
        return int(match.group(1))

    @classmethod
    def _parse_skill_levels(cls, text: str) -> dict[str, int | str]:
        skills: dict[str, int | str] = {}
        for skill_name, aliases in cls._SKILL_ALIASES.items():
            for alias in aliases:
                match = re.search(rf"{re.escape(alias)}\s*(?::|\uFF1A)?\s*([A-F]|\d{{1,2}})", text, re.IGNORECASE)
                if match is not None:
                    value = match.group(1).upper()
                    skills[skill_name] = int(value) if value.isdigit() else value
                    break
        return skills

    @classmethod
    def _parse_stat_line(cls, text: str) -> dict[str, str] | None:
        clean = cls._clean_text(text)
        for stat_name, aliases in cls._STAT_ALIASES.items():
            for alias in aliases:
                match = re.search(
                    rf"{re.escape(alias)}\s*(?::|\uFF1A)?\s*([+\-]?\d+(?:\.\d+)?%?)",
                    clean,
                    re.IGNORECASE,
                )
                if match is not None:
                    return {"name": stat_name, "value": match.group(1), "raw": clean}
        return None

    @classmethod
    def _merge_character_fields(cls, current: dict[str, Any], candidate: dict[str, Any]) -> None:
        for field in ("name", "level", "ascension", "rarity", "element", "weapon_type"):
            value = candidate.get(field)
            if value not in (None, "") and current.get(field) in (None, ""):
                current[field] = value

        if candidate.get("skill_levels"):
            current.setdefault("skill_levels", {}).update(candidate["skill_levels"])

    @classmethod
    def _parse_character_candidate(cls, line: str) -> dict[str, Any]:
        clean = cls._clean_text(line)
        return {
            "name": cls._parse_name(clean),
            "level": cls._parse_level(clean),
            "ascension": cls._parse_ascension(clean),
            "rarity": cls._parse_rarity(clean),
            "element": cls._parse_element(clean),
            "weapon_type": cls._parse_weapon_type(clean),
            "skill_levels": cls._parse_skill_levels(clean),
        }

    @classmethod
    def _parse_characters_from_lines(cls, lines: list[str]) -> list[dict[str, Any]]:
        characters: list[dict[str, Any]] = []
        current: dict[str, Any] = {}

        def flush() -> None:
            if not current:
                return
            if any(
                current.get(field) not in (None, "", {})
                for field in ("name", "level", "ascension", "rarity", "element", "weapon_type", "skill_levels")
            ):
                characters.append(
                    {
                        "name": current.get("name", ""),
                        "level": current.get("level"),
                        "ascension": current.get("ascension"),
                        "rarity": current.get("rarity"),
                        "element": current.get("element"),
                        "weapon_type": current.get("weapon_type"),
                        "skill_levels": current.get("skill_levels", {}),
                    }
                )

        for line in lines:
            candidate = cls._parse_character_candidate(line)
            has_data = any(value not in (None, "", {}) for value in candidate.values())
            if not has_data:
                continue

            if candidate.get("name") and current.get("name"):
                flush()
                current = {}

            cls._merge_character_fields(current, candidate)

        flush()
        return characters

    @classmethod
    def _parse_equipment_blocks(cls, lines: list[str]) -> list[list[str]]:
        if not lines:
            return []

        blocks: list[list[str]] = []
        current: list[str] = []
        for line in lines:
            current_has_position = any(cls._parse_position(item) is not None for item in current)
            current_has_stats = any(cls._parse_stat_line(item) is not None for item in current)
            starts_new = bool(current) and (
                (cls._parse_position(line) is not None and current_has_position)
                or (cls._parse_name(line) and current_has_stats)
            )
            if starts_new:
                blocks.append(current)
                current = [line]
            else:
                current.append(line)
        if current:
            blocks.append(current)
        return blocks

    @classmethod
    def _parse_equipment_entry(cls, lines: list[str]) -> dict[str, Any] | None:
        if not lines:
            return None

        entry: dict[str, Any] = {
            "name": None,
            "position": None,
            "level": None,
            "rarity": None,
            "main_stat": None,
            "sub_stats": [],
        }
        for line in lines:
            clean = cls._clean_text(line)
            if entry["name"] is None:
                name = cls._parse_name(clean)
                if name:
                    entry["name"] = name
            if entry["position"] is None:
                entry["position"] = cls._parse_position(clean)
            if entry["level"] is None:
                entry["level"] = cls._parse_enhancement_level(clean)
            if entry["rarity"] is None:
                entry["rarity"] = cls._parse_rarity(clean)

            stat = cls._parse_stat_line(clean)
            if stat is not None:
                if entry["main_stat"] is None:
                    entry["main_stat"] = stat
                else:
                    entry["sub_stats"].append(stat)

        if not any(entry.values()):
            return None
        return entry

    async def extract_stamina(self) -> ExtractionResult:
        errors: list[str] = []
        raw_text = ""
        try:
            image = self._screenshot()
            raw_text = self._ocr_text(image, self._STAMINA_REGION, errors=errors, context="extract_stamina")
            current, max_value = self._parse_stamina(raw_text)
            if current is None or max_value is None:
                errors.append("unable to parse stamina")
            return ExtractionResult(
                success=current is not None and max_value is not None,
                data={"current": current, "max": max_value},
                raw_ocr_text=raw_text,
                errors=errors or None,
            )
        except Exception as exc:
            self._safe_error(errors, "extract_stamina", exc)
            return ExtractionResult(False, {"current": None, "max": None}, raw_ocr_text=raw_text, errors=errors)

    async def extract_characters(self) -> ExtractionResult:
        errors: list[str] = []
        raw_text = ""
        try:
            image = self._screenshot()
            raw_text = self._ocr_text(image, errors=errors, context="extract_characters")
            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            characters = self._parse_characters_from_lines(lines)

            if not characters and raw_text:
                errors.append("no character entries parsed")

            return ExtractionResult(
                success=bool(characters),
                data={"characters": characters},
                raw_ocr_text=raw_text,
                errors=errors or None,
            )
        except Exception as exc:
            self._safe_error(errors, "extract_characters", exc)
            return ExtractionResult(False, {"characters": []}, raw_ocr_text=raw_text, errors=errors)

    async def extract_inventory(self, material_name: str | None = None) -> ExtractionResult:
        errors: list[str] = []
        raw_text = ""
        try:
            image = self._screenshot()
            raw_text = self._ocr_text(image, errors=errors, context="extract_inventory")
            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            materials: list[dict[str, Any]] = []

            for line in lines:
                parsed = self._parse_quantity(line)
                if parsed is None:
                    continue
                name, quantity = parsed
                if material_name and material_name.lower() not in name.lower():
                    continue
                materials.append({"name": name, "quantity": quantity, "rarity": self._parse_rarity(line)})

            if material_name and not materials:
                errors.append(f"material '{material_name}' not found")

            return ExtractionResult(
                success=bool(materials),
                data={"materials": materials},
                raw_ocr_text=raw_text,
                errors=errors or None,
            )
        except Exception as exc:
            self._safe_error(errors, "extract_inventory", exc)
            return ExtractionResult(False, {"materials": []}, raw_ocr_text=raw_text, errors=errors)

    async def extract_equipment(self) -> ExtractionResult:
        errors: list[str] = []
        raw_text = ""
        try:
            image = self._screenshot()
            raw_text = self._ocr_text(image, errors=errors, context="extract_equipment")
            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            equipment = []
            for block in self._parse_equipment_blocks(lines):
                entry = self._parse_equipment_entry(block)
                if entry is not None:
                    equipment.append(entry)
            if not equipment and raw_text:
                errors.append("no equipment entries parsed")
            return ExtractionResult(
                success=bool(equipment),
                data={"equipment": equipment},
                raw_ocr_text=raw_text,
                errors=errors or None,
            )
        except Exception as exc:
            self._safe_error(errors, "extract_equipment", exc)
            return ExtractionResult(False, {"equipment": []}, raw_ocr_text=raw_text, errors=errors)
