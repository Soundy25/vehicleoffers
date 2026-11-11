# Chemin exact : scripts/probe_site.py [NEW]
# Chemin exact : scripts/probe_site.py [NEW]
"""Manually probe one authorized HTTPS page without retries or data extraction."""

import argparse
import sys

from playwright.sync_api import Error as PlaywrightError

from scraper.browser_engine import visit_once


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="One HTTPS URL you are authorized to access.")
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=20_000,
        help="Navigation timeout in milliseconds (default: 20000).",
    )
    args = parser.parse_args()

    try:
        result = visit_once(args.url, timeout_ms=args.timeout_ms)
    except ValueError as error:
        parser.error(str(error))
    except PlaywrightError as error:
        print(f"Navigation failed ({type(error).__name__}); no retry was attempted.", file=sys.stderr)
        return 2

    print(f"HTTP status: {result.status_code if result.status_code is not None else 'unavailable'}")
    print(f"Page title: {result.title or '(empty)'}")
    if result.access_limited:
        print("Access limitation or challenge detected; stopping.")
        return 3
    print("No common access-denial signal detected. This does not imply permission for further automation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
