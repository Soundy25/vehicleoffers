# Chemin exact : scraper/gas_client.py [NEW]
import hashlib
import hmac
import json
import time
from typing import Any
from uuid import uuid4

import aiohttp


class GasWebAppClient:
    def __init__(
        self,
        web_app_url: str,
        api_secret: str,
        hmac_secret: str,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.web_app_url = web_app_url
        self.api_secret = api_secret
        self.hmac_secret = hmac_secret
        self.timeout_seconds = timeout_seconds

    async def fetch_keys(self) -> list[str]:
        """Read existing vehicle IDs from GAS before writing."""
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                self.web_app_url,
                params={"action": "get_config", "secret": self.api_secret},
            ) as response:
                if response.status != 200:
                    raise RuntimeError(f"GAS returned HTTP {response.status} for the read request")
                result = await response.json()

        if not isinstance(result, dict):
            raise RuntimeError("GAS returned a non-object JSON response for the read request")
        if result.get("status") != "success":
            raise RuntimeError(f"GAS rejected the read request: {result.get('message', 'unknown error')}")
        keys = result.get("keys")
        if not isinstance(keys, list) or not all(isinstance(key, str) for key in keys):
            raise RuntimeError("GAS returned an invalid keys list")
        return keys

    async def execute_write_test(self) -> dict[str, Any]:
        """Insert conforming and non-conforming sample rows after checking their URLs."""
        keys = await self.fetch_keys()
        sample_url = "https://www.testsite.fr/ad/voitures/3206865999"
        non_conforming_url = sample_url + "?test=non-conforme"
        if sample_url in keys or non_conforming_url in keys:
            raise RuntimeError("One or more sample vehicle URLs already exist in the sheet")

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        payload = {
            "offers": [
                [
                    "29/09/2026",
                    "ToyTest yaya",
                    9999,
                    99999,
                    0,
                    "MaVille",
                    999,
                    "NC",
                    "CONFORME",
                    "AlerteRisque",
                    "Commentaire",
                    "TESTAUTO",
                    "SOURCETEST",
                    sample_url,
                ],
                [
                    "29/09/2026",
                    "ToyTest yaya",
                    9999,
                    99999,
                    0,
                    "MaVille",
                    999,
                    "NC",
                    "NON CONFORME",
                    "AlerteRisque",
                    "Commentaire",
                    "TESTAUTO",
                    "SOURCETEST",
                    non_conforming_url,
                ],
            ],
            "log": {
                "total_count": 2
            },
            "timestamp": int(time.time()),
            "request_id": str(uuid4()),
        }
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(
            self.hmac_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                self.web_app_url,
                params={"signature": signature},
                data=body,
                headers={
                    "Content-Type": "application/json",
                },
            ) as response:
                if response.status != 200:
                    raise RuntimeError(f"GAS returned HTTP {response.status}")
                result = await response.json()

        if not isinstance(result, dict):
            raise RuntimeError("GAS returned a non-object JSON response")
        if result.get("status") != "success":
            raise RuntimeError(f"GAS rejected the write test: {result.get('message', 'unknown error')}")
        return result