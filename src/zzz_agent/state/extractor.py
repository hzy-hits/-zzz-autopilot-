"""Screenshot -> structured game state extraction.

The extractor is best-effort and must not crash on OCR or framework issues.
It returns partial results alongside errors so higher layers can decide how
to proceed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


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

    def __init__(self, z_ctx: object) -> None:
        self._z_ctx = z_ctx

    def _safe_error(self, errors: list[str], context: str, exc: Exception) -> None:
        errors.append(f"{context}: {type(exc).__name__}: {exc}")

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

    def _ocr_text(self, image: Any, region: tuple[int, int, int, int] | None = None) -> str:
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
        except Exception:
            pass

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
            if ocr is not None and hasattr(ocr, "run_ocr_single_line"):
                return str(ocr.run_ocr_single_line(target))
        except Exception:
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
        name_match = re.match(r"([A-Za-z\u4e00-\u9fff][A-Za-z0-9_\-\u4e00-\u9fff ]{1,40})", clean)
        return name_match.group(1).strip() if name_match else clean

    @staticmethod
    def _parse_quantity(line: str) -> tuple[str, int] | None:
        clean = re.sub(r"\s+", " ", line).strip()
        match = re.search(r"(.+?)\s+([0-9]{1,6})$", clean)
        if match is None:
            return None
        return match.group(1).strip(), int(match.group(2))

    async def extract_stamina(self) -> ExtractionResult:
        errors: list[str] = []
        raw_text = ""
        try:
            image = self._screenshot()
            raw_text = self._ocr_text(image, self._STAMINA_REGION)
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
            raw_text = self._ocr_text(image)
            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            characters: list[dict[str, Any]] = []

            for line in lines:
                level = self._parse_level(line)
                ascension = self._parse_ascension(line)
                name = self._parse_name(line)
                if not name and level is None and ascension is None:
                    continue
                characters.append({"name": name, "level": level, "ascension": ascension})

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
            raw_text = self._ocr_text(image)
            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            materials: list[dict[str, Any]] = []

            for line in lines:
                parsed = self._parse_quantity(line)
                if parsed is None:
                    continue
                name, quantity = parsed
                if material_name and material_name.lower() not in name.lower():
                    continue
                materials.append({"name": name, "quantity": quantity})

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
            raw_text = self._ocr_text(image)
            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            equipment = [{"text": line} for line in lines]
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
