# Chemin exact : tests/test_browser_engine.py [NEW]
# Chemin exact : tests/test_browser_engine.py [NEW]
import unittest

from scraper.browser_engine import is_access_limited, visit_once


class TestBrowserEngine(unittest.TestCase):
    def test_visit_once_requires_absolute_https_url(self) -> None:
        for url in ("", "http://example.com", "/search"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    visit_once(url)

    def test_visit_once_requires_positive_timeout(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            visit_once("https://example.com", timeout_ms=0)

    def test_access_denial_statuses_are_limited(self) -> None:
        for status in (401, 403, 429):
            with self.subTest(status=status):
                self.assertTrue(is_access_limited(status, "", ""))

    def test_challenge_page_is_limited_even_with_success_status(self) -> None:
        self.assertTrue(is_access_limited(200, "Vérification", "Veuillez confirmer que vous êtes humain"))

    def test_regular_page_is_not_classified_as_limited(self) -> None:
        self.assertFalse(is_access_limited(200, "Annonces auto", "Toyota Yaris occasion"))


if __name__ == "__main__":
    unittest.main()
