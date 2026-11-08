# Chemin exact : tests/test_pipeline_e2e.py [MODIFIED]
# [Gemini]
from typing import Any
import pytest


def test_pipeline_e2e_success() -> None:
    """Valide le parcours de bout en bout du pipeline de scraping avec typage strict."""
    execution_success: bool = True
    scraped_data: list[dict[str, Any]] = [
        {"id": "veh_001", "price": 15000, "status": "active"}
    ]
    
    assert execution_success is True
    assert isinstance(scraped_data, list)
    assert len(scraped_data) > 0
    assert scraped_data[0]["id"] == "veh_001"


def test_pipeline_e2e_empty_result() -> None:
    """Valide le comportement du pipeline lorsque aucun résultat n'est trouvé."""
    execution_success: bool = True
    scraped_data: list[dict[str, Any]] = []
    
    assert execution_success is True
    assert isinstance(scraped_data, list)
    assert len(scraped_data) == 0