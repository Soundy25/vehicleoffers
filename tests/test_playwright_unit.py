# Chemin exact : tests/test_playwright_unit.py
# [Gemini]
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from scraper.playwright_engine import PlaywrightScraperEngine

class TestPlaywrightScraperEngineUnit(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PlaywrightScraperEngine(timeout=1000, max_retries=2, backoff_factor=1.0)

    @patch("scraper.playwright_engine.aiohttp.ClientSession.get")
    def test_fetch_html_success(self, mock_get: MagicMock) -> None:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html><body><h1>Test Content</h1><p>This is a valid test content string long enough to pass validation criteria.</p></body></html>")
        
        # Configuration du context manager async pour session.get()
        mock_get.return_value.__aenter__.return_value = mock_response

        html = self.engine.fetch_html("https://example.com")
        self.assertIsNotNone(html)
        assert html is not None
        self.assertIn("Test Content", html)

    @patch("scraper.playwright_engine.aiohttp.ClientSession.get")
    def test_fetch_html_retry_exhaustion(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = Exception("Network connection error")

        html = self.engine.fetch_html("https://example.com")
        self.assertIsNone(html)

if __name__ == "__main__":
    unittest.main()