# tests/test_parser.py
import pytest
from typing import Any, Dict, List
from parsers.base_parser import BaseParser, VehicleData

class DummyParser(BaseParser):
    """Implémentation concrète minimale pour valider la classe abstraite BaseParser."""
    async def parse(self) -> List[Dict[str, Any]]:
        return [{"title": "Véhicule Test", "price": 15000.0, "url": "https://example.com"}]

@pytest.mark.asyncio
async def test_base_parser_initialization() -> None:
    """Vérifie l'initialisation correcte et le rejet strict des contenus vides."""
    with pytest.raises(ValueError):
        DummyParser("")
    
    parser = DummyParser("<html><body>Test</body></html>")
    assert parser.html_content == "<html><body>Test</body></html>"

@pytest.mark.asyncio
async def test_base_parser_parse_and_validate() -> None:
    """Vérifie le comportement asynchrone de parse et la validation Pydantic intégrée."""
    parser = DummyParser("<html></html>")
    results = await parser.parse()
    assert len(results) == 1
    
    cleaned = parser.validate_and_clean(results[0])
    assert cleaned["title"] == "Véhicule Test"
    assert cleaned["price"] == 15000.0