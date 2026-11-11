import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from scraper.road_distance import RoadDistanceCalculator


@pytest.mark.asyncio
async def test_calculates_driving_distance_from_commune_to_besancon() -> None:
    requests: list[tuple[str, dict[str, str]]] = []

    async def get_json(url: str, params: dict[str, str]) -> Any:
        requests.append((url, params))
        if "nominatim" in url:
            return [{"lat": "47.1", "lon": "6.2"} if params["q"].startswith("Dole") else {
                "lat": "47.2",
                "lon": "6.0",
            }]
        return {"code": "Ok", "routes": [{"distance": 45200}]}

    calculator = RoadDistanceCalculator(json_get=get_json)
    with patch("scraper.road_distance.asyncio.sleep", new_callable=AsyncMock) as sleep:
        distance = await calculator.from_commune_to_besancon("Dole")

    assert distance == 45.2
    assert len(requests) == 3
    assert requests[0][1]["q"] == "Besançon 25000, France"
    assert requests[1][1]["q"] == "Dole, France"
    assert "6.2,47.1;6.0,47.2" in requests[2][0]
    sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_caches_geocodes_and_road_distance() -> None:
    requests: list[str] = []

    async def get_json(url: str, params: dict[str, str]) -> Any:
        requests.append(url)
        if "nominatim" in url:
            return [{"lat": "47.2", "lon": "6.0"}]
        return {"code": "Ok", "routes": [{"distance": 1000}]}

    calculator = RoadDistanceCalculator(json_get=get_json)
    with patch("scraper.road_distance.asyncio.sleep", new_callable=AsyncMock):
        assert await calculator.from_commune_to_besancon("Besançon") == 1
        assert await calculator.from_commune_to_besancon("Besançon") == 1
    assert len(requests) == 3


@pytest.mark.asyncio
async def test_unresolved_commune_returns_unknown_distance() -> None:
    async def get_json(url: str, params: dict[str, str]) -> Any:
        if "nominatim" in url and params["q"].startswith("Dole"):
            return []
        if "nominatim" in url:
            return [{"lat": "47.2", "lon": "6.0"}]
        raise AssertionError("A route should not be requested without both geocodes")

    calculator = RoadDistanceCalculator(json_get=get_json)
    with patch("scraper.road_distance.asyncio.sleep", new_callable=AsyncMock):
        assert await calculator.from_commune_to_besancon("Dole") is None


def test_empty_commune_does_not_make_requests() -> None:
    get_json = AsyncMock()
    calculator = RoadDistanceCalculator(json_get=get_json)
    assert asyncio.run(calculator.from_commune_to_besancon(None)) is None
    get_json.assert_not_awaited()
