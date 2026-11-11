# Chemin exact : scraper/gas_client.py [NEW]
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import aiohttp


# Chemin exact : scraper/gas_client.py [MODIFIÉ]
@dataclass(frozen=True)
class GasVehicleCriteria:
    brand: str
    models: tuple[str, ...]
    budget_max: float
    mileage_max: float
    year_min: float
    energy: str
    seats: float
    distance_max_km: float
    exclusions: tuple[str, ...]


@dataclass(frozen=True)
class GasConfiguration:
    keys: tuple[str, ...]
    targets: tuple[str, ...]
    criteria: tuple[GasVehicleCriteria, ...]


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
        result = await self._fetch_config_response()
        keys = result.get("keys") if isinstance(result, dict) else None
        if not isinstance(keys, list) or not all(isinstance(key, str) for key in keys):
            raise RuntimeError("GAS returned an invalid keys list")
        return keys

    async def fetch_config(self) -> GasConfiguration:
        """Read deduplication keys, source URLs, and validated vehicle criteria."""
        result = await self._fetch_config_response()
        if not isinstance(result, dict):
            raise RuntimeError("GAS returned a non-object JSON response for the read request")

        keys = result.get("keys")
        targets = result.get("targets")
        raw_criteria = result.get("criteria")
        if not isinstance(keys, list) or not all(isinstance(key, str) for key in keys):
            raise RuntimeError("GAS returned an invalid keys list")
        if not isinstance(targets, list) or not all(isinstance(target, str) for target in targets):
            raise RuntimeError("GAS returned an invalid targets list")
        if not isinstance(raw_criteria, list):
            raise RuntimeError("GAS returned an invalid criteria list")

        criteria = tuple(self._parse_criteria(item) for item in raw_criteria)
        if not criteria:
            raise RuntimeError("GAS returned an empty criteria list")
        return GasConfiguration(tuple(keys), tuple(targets), criteria)

    def _parse_criteria(self, value: Any) -> GasVehicleCriteria:
        if not isinstance(value, dict):
            raise RuntimeError("GAS returned an invalid vehicle criteria entry")
        brand = value.get("brand")
        models = value.get("models")
        energy = value.get("energy")
        exclusions = value.get("exclusions")
        if not isinstance(brand, str) or not brand.strip():
            raise RuntimeError("GAS returned an invalid criteria brand")
        if not isinstance(models, list) or not models or not all(
            isinstance(model, str) and model.strip() for model in models
        ):
            raise RuntimeError("GAS returned an invalid criteria models list")
        if not isinstance(energy, str) or not energy.strip():
            raise RuntimeError("GAS returned an invalid criteria energy")
        if not isinstance(exclusions, list) or not all(isinstance(item, str) for item in exclusions):
            raise RuntimeError("GAS returned an invalid criteria exclusions list")

        numeric_fields = (
            "budget_max",
            "mileage_max",
            "year_min",
            "seats",
            "distance_max_km",
        )
        numbers: dict[str, float] = {}
        for field in numeric_fields:
            number = value.get(field)
            if isinstance(number, bool) or not isinstance(number, (int, float)):
                raise RuntimeError(f"GAS returned an invalid numeric criterion: {field}")
            numbers[field] = float(number)

        return GasVehicleCriteria(
            brand=brand.strip(),
            models=tuple(model.strip() for model in models),
            budget_max=numbers["budget_max"],
            mileage_max=numbers["mileage_max"],
            year_min=numbers["year_min"],
            energy=energy.strip(),
            seats=numbers["seats"],
            distance_max_km=numbers["distance_max_km"],
            exclusions=tuple(exclusions),
        )

    async def _fetch_config_response(self) -> Any:
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
        return result

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
                    "Toyota Yaris hybride test conforme",
                    9999,
                    99999,
                    2021,
                    "Besançon",
                    100,
                    "Oui",
                    "CONFORME",
                    "AlerteRisque",
                    "Commentaire",
                    "Garage test",
                    "L'Argus",
                    sample_url,
                ],
                [
                    "29/09/2026",
                    "Toyota Yaris hybride test non conforme",
                    9999,
                    120001,
                    2021,
                    "Besançon",
                    100,
                    "Oui",
                    "NON CONFORME",
                    "AlerteRisque",
                    "Commentaire",
                    "Garage test",
                    "L'Argus",
                    non_conforming_url,
                ],
            ],
            "vehicle_facts": {
                sample_url: {
                    "make": "Toyota",
                    "model": "Yaris",
                    "energy": "Hybride",
                    "seats": 5,
                    "description": "Ligne de test"
                },
                non_conforming_url: {
                    "make": "Toyota",
                    "model": "Yaris",
                    "energy": "Hybride",
                    "seats": 5,
                    "description": "Ligne de test"
                }
            },
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