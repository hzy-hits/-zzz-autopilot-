"""Tests for screenshot-to-state parsing heuristics."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from zzz_agent.state.extractor import StateExtractor


def _extractor_from_text(text: str) -> StateExtractor:
    ocr_results = [SimpleNamespace(data=line) for line in text.splitlines()]
    z_ctx = SimpleNamespace(
        controller=SimpleNamespace(screenshot=lambda: (0.0, object())),
        ocr_service=SimpleNamespace(get_ocr_result_list=lambda _image: ocr_results),
        ocr=None,
    )
    return StateExtractor(z_ctx)


@pytest.mark.asyncio
async def test_extract_characters_parses_structured_fields() -> None:
    extractor = _extractor_from_text(
        "\n".join(
            [
                "Anby",
                "Lv. 50 Ascension 3",
                "A-rank Electric Slash",
                "Basic Attack 8",
                "Dodge 7",
                "Assist 6",
                "Special Attack 9",
                "Chain Attack 10",
                "Core E",
                "Billy Lv. 40 Breakthrough 2 A-rank Physical Pierce Basic Attack 7 Dodge 6 Chain Attack 8 Core D",
            ]
        )
    )

    result = await extractor.extract_characters()

    assert result.success is True
    assert len(result.data["characters"]) == 2
    assert result.data["characters"][0] == {
        "name": "Anby",
        "level": 50,
        "ascension": 3,
        "rarity": "A",
        "element": "Electric",
        "weapon_type": "Slash",
        "skill_levels": {
            "basic_attack": 8,
            "dodge": 7,
            "assist": 6,
            "special_attack": 9,
            "chain_attack": 10,
            "core_skill": "E",
        },
    }
    assert result.data["characters"][1]["name"] == "Billy"
    assert result.data["characters"][1]["weapon_type"] == "Pierce"


@pytest.mark.asyncio
async def test_extract_inventory_parses_rarity_and_filter() -> None:
    extractor = _extractor_from_text(
        "\n".join(
            [
                "S Advanced Ether Core x12",
                "A Ether Chip 34",
                "B Dennies 125,000",
            ]
        )
    )

    result = await extractor.extract_inventory(material_name="Ether")

    assert result.success is True
    assert result.data["materials"] == [
        {"name": "Advanced Ether Core", "quantity": 12, "rarity": "S"},
        {"name": "Ether Chip", "quantity": 34, "rarity": "A"},
    ]


@pytest.mark.asyncio
async def test_extract_equipment_parses_slot_main_and_substats() -> None:
    extractor = _extractor_from_text(
        "\n".join(
            [
                "Woodpecker Electro",
                "Slot 4",
                "S-rank",
                "+15",
                "CRIT Rate 24%",
                "ATK +19",
                "HP +112",
                "PEN Ratio 8%",
            ]
        )
    )

    result = await extractor.extract_equipment()

    assert result.success is True
    assert result.data["equipment"] == [
        {
            "name": "Woodpecker Electro",
            "position": 4,
            "level": 15,
            "rarity": "S",
            "main_stat": {"name": "CRIT Rate", "value": "24%", "raw": "CRIT Rate 24%"},
            "sub_stats": [
                {"name": "ATK", "value": "+19", "raw": "ATK +19"},
                {"name": "HP", "value": "+112", "raw": "HP +112"},
                {"name": "PEN Ratio", "value": "8%", "raw": "PEN Ratio 8%"},
            ],
        }
    ]


@pytest.mark.asyncio
async def test_extract_inventory_reports_ocr_backend_failures() -> None:
    class BrokenOcrService:
        def get_ocr_result_list(self, _image):
            raise RuntimeError("ocr_service broke")

    class BrokenOcr:
        def ocr(self, _image):
            raise ValueError("ocr broke")

        def run_ocr_single_line(self, _image):
            raise TypeError("single line broke")

    z_ctx = SimpleNamespace(
        controller=SimpleNamespace(screenshot=lambda: (0.0, object())),
        ocr_service=BrokenOcrService(),
        ocr=BrokenOcr(),
    )
    extractor = StateExtractor(z_ctx)

    result = await extractor.extract_inventory()

    assert result.success is False
    assert result.errors is not None
    assert any("extract_inventory.ocr_service" in error for error in result.errors)
    assert any("extract_inventory.ocr" in error for error in result.errors)
    assert any("extract_inventory.run_ocr_single_line" in error for error in result.errors)
