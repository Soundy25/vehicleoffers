# Chemin exact : tests/test_playwright_engine.py
# [Gemini]
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from scraper.playwright_engine import PlaywrightScraperEngine

class TestPlaywrightScraperEngineIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PlaywrightScraperEngine(timeout=2000, max_retries=2, backoff_factor=1.0)

    @patch("scraper.playwright_engine.aiohttp.ClientSession.get")
    def test_fetch_page_content_alias(self, mock_get: MagicMock) -> None:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html><body><div class='vehicle-item'>Valid vehicle offer content string long enough for validation.</div></body></html>")
        
        mock_get.return_value.__aenter__.return_value = mock_response

        content = self.engine.fetch_page_content("https://example.com/offers")
        self.assertIsNotNone(content)
        assert content is not None
        self.assertIn("vehicle-item", content)

if __name__ == "__main__":
    unittest.main()