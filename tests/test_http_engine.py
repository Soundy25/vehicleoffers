# Chemin exact : tests/test_http_engine.py [NEW]
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from scraper.http_engine import HttpScraperEngine


class TestHttpScraperEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = HttpScraperEngine(
            timeout_seconds=1.0,
            max_retries=2,
            backoff_factor=1.0,
        )

    @patch("scraper.http_engine.aiohttp.ClientSession")
    def test_fetch_html_rejects_non_http_urls(self, mock_session: MagicMock) -> None:
        for url in ("", "ftp://example.com/file"):
            with self.subTest(url=url):
                self.assertIsNone(self.engine.fetch_html(url))

        mock_session.assert_not_called()

    @patch("scraper.http_engine.aiohttp.ClientSession.get")
    def test_fetch_html_success(self, mock_get: MagicMock) -> None:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html><h1>Test Content</h1></html>")
        mock_get.return_value.__aenter__.return_value = mock_response

        html = self.engine.fetch_html("https://example.com")

        self.assertEqual(html, "<html><h1>Test Content</h1></html>")

    @patch("scraper.http_engine.aiohttp.ClientSession.get")
    def test_fetch_html_stops_after_access_is_limited(self, mock_get: MagicMock) -> None:
        mock_response = AsyncMock()
        mock_response.status = 429
        mock_get.return_value.__aenter__.return_value = mock_response

        self.assertIsNone(self.engine.fetch_html("https://example.com"))
        mock_get.assert_called_once()

    @patch("scraper.http_engine.aiohttp.ClientSession.get")
    def test_fetch_html_retries_network_errors(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = aiohttp.ClientConnectionError("Network connection error")

        self.assertIsNone(self.engine.fetch_html("https://example.com"))
        self.assertEqual(mock_get.call_count, 2)


if __name__ == "__main__":
    unittest.main()