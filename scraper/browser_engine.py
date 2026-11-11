# Chemin exact : scraper/browser_engine.py [NEW]
"""One-shot, standard Playwright navigation for manually authorized URLs."""

from dataclasses import dataclass
import re
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


_CHALLENGE_TERMS = re.compile(
    r"\b(captcha|robot|automated|automation|vérification|verification|"
    r"unusual traffic|access denied|accès refusé|blocked|bloqué)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BrowserVisit:
    status_code: int | None
    title: str
    access_limited: bool
    html: str | None = None


def is_access_limited(status_code: int | None, title: str, body_text: str) -> bool:
    """Recognize common access-denial responses and stop-worthy challenge pages."""
    if status_code in (401, 403, 429):
        return True
    return bool(_CHALLENGE_TERMS.search(f"{title} {body_text[:2000]}"))


def visit_once(url: str, timeout_ms: int = 20_000) -> BrowserVisit:
    """Load one HTTPS page with default Chromium settings and no retries or interactions."""
    parsed_url = urlsplit(url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise ValueError("Only absolute HTTPS URLs are accepted.")
    if timeout_ms <= 0:
        raise ValueError("timeout_ms must be positive.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            try:
                page = context.new_page()
                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=timeout_ms,
                )
                title = page.title()
                status_code = response.status if response else None
                if status_code in (401, 403, 429):
                    return BrowserVisit(
                        status_code=status_code,
                        title=title,
                        access_limited=True,
                    )
                body_text = page.locator("body").inner_text(timeout=2_000)
                if is_access_limited(status_code, title, body_text):
                    return BrowserVisit(
                        status_code=status_code,
                        title=title,
                        access_limited=True,
                    )
                return BrowserVisit(
                    status_code=status_code,
                    title=title,
                    access_limited=False,
                    html=page.content(),
                )
            finally:
                context.close()
        finally:
            browser.close()
