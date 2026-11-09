# Chemin exact : scripts/test_gas_write.py [NEW]
import asyncio
import json
import os
import sys

import aiohttp

from scraper.gas_client import GasWebAppClient


def main() -> int:
    web_app_url = os.environ.get("GAS_WEB_APP_URL", "")
    api_secret = os.environ.get("API_SECRET", "")
    hmac_secret = os.environ.get("HMAC_SECRET", "")
    if not web_app_url or not api_secret or not hmac_secret:
        print("GAS_WEB_APP_URL, API_SECRET et HMAC_SECRET doivent être définis.", file=sys.stderr)
        return 2

    client = GasWebAppClient(
        web_app_url=web_app_url,
        api_secret=api_secret,
        hmac_secret=hmac_secret,
    )
    try:
        result = asyncio.run(client.execute_write_test())
    except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError, ValueError) as error:
        print(f"Échec du test d'écriture GAS : {error}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())