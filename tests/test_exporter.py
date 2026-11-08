# Chemin exact : tests/test_exporter.py [NEW]
"""
Description : Tests unitaires asynchrones pour SecureDataExporter, garantissant
l'intégrité de la persistance des données et la gestion robuste des cas d'erreur.
"""

import pytest
from pathlib import Path
from scraper.exporter import SecureDataExporter

@pytest.mark.asyncio
async def test_exporter_empty_data(tmp_path: Path) -> None:
    """Vérifie que l'export ignore les listes de données vides sans corrompre le système."""
    exporter = SecureDataExporter(output_dir=str(tmp_path))
    result = await exporter.export_to_json("output.json", [])
    assert result is False

@pytest.mark.asyncio
async def test_exporter_nominal_flow(tmp_path: Path) -> None:
    """Vérifie l'export nominal réussi vers un fichier JSON valide."""
    exporter = SecureDataExporter(output_dir=str(tmp_path))
    sample_data = [{"title": "Renault Megane", "price": 12000.0}]
    
    result = await exporter.export_to_json("vehicles.json", sample_data)
    assert result is True
    
    target_file = tmp_path / "vehicles.json"
    assert target_file.exists()
    assert "Renault Megane" in target_file.read_text(encoding="utf-8")