# Chemin exact : tests/test_engine_unit.py [NEW]
"""
Description : Tests unitaires ciblés pour le moteur de scraping asynchrone,
garantissant la validation du filtrage d'URL en mode Zero Trust.
"""

import pytest
from scraper.engine import SecureScraperEngine

@pytest.mark.asyncio
async def test_scraper_engine_rejects_non_http_urls() -> None:
    """Vérifie que les protocoles non sécurisés ou non HTTP sont immédiatement rejetés."""
    engine = SecureScraperEngine(timeout_seconds=5.0, max_retries=3)
    
    # Test avec un protocole non valide
    result_ftp = await engine.fetch_url("ftp://example.com/file")
    assert result_ftp is None

    # Test avec une chaîne vide
    result_empty = await engine.fetch_url("")
    assert result_empty is None