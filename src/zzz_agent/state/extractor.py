"""Screenshot -> structured game state extraction.

Converts raw screenshots into structured data by combining:
  - Template matching (framework's TemplateMatcher)
  - OCR text recognition (framework's OcrMatcher)
  - Region-of-interest definitions

TODO(codex): Full implementation. Acceptance criteria:
  - Extract stamina (current/max) from main UI overlay
  - Extract character info (name, level, ascension) from character panel
  - Extract material quantities from inventory panel
  - Each extractor handles OCR errors gracefully (return None on failure, not crash)
  - All extractors work at 1920x1080 resolution (framework default)
"""

from __future__ import annotations

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
    """Extracts structured game state from screenshots.

    Uses the framework's OCR and template matching capabilities to parse
    game UI into structured data.

    Args:
        z_ctx: The framework's OneDragonContext instance.
    """

    def __init__(self, z_ctx: object) -> None:
        self._z_ctx = z_ctx

    async def extract_stamina(self) -> ExtractionResult:
        """Extract current and max stamina from the main UI.

        The stamina display is typically in the top-right corner of the main game screen.

        Returns:
            ExtractionResult with data: {"current": 180, "max": 240}

        TODO(codex): Implement.
        - Take screenshot via z_ctx.controller.screenshot()
        - Crop to stamina region (top-right area)
        - OCR the cropped region
        - Parse "180/240" format into current and max
        """
        raise NotImplementedError

    async def extract_characters(self) -> ExtractionResult:
        """Extract character list with levels from the character panel.

        Assumes the character panel is currently visible.

        Returns:
            ExtractionResult with data: {
                "characters": [
                    {"name": "Lina", "level": 52, "ascension": 4},
                    ...
                ]
            }

        TODO(codex): Implement.
        - Screenshot the character panel
        - OCR character names and levels
        - Match against known character templates if available
        """
        raise NotImplementedError

    async def extract_inventory(self, material_name: str | None = None) -> ExtractionResult:
        """Extract material quantities from the inventory.

        Args:
            material_name: Optional filter for a specific material.

        Returns:
            ExtractionResult with data: {
                "materials": [
                    {"name": "Ether Core", "quantity": 5},
                    ...
                ]
            }

        TODO(codex): Implement.
        - Screenshot inventory panel
        - OCR item names and quantities
        - Match against known material templates
        """
        raise NotImplementedError

    async def extract_equipment(self) -> ExtractionResult:
        """Extract equipped drive disc information.

        Returns:
            ExtractionResult with data about currently equipped items.

        TODO(codex): Implement.
        """
        raise NotImplementedError
