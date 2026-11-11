"""Estimate driving distance between an advertised commune and Besançon."""

import asyncio
import logging
import time
import unicodedata
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

_GEOCODER_URL = "https://nominatim.openstreetmap.org/search"
_ROUTER_URL = "https://router.project-osrm.org/route/v1/driving"
_ORIGIN_QUERY = "Besançon 25000, France"
_USER_AGENT = "vehicleoffers/1.0 (personal daily vehicle search)"
_MIN_GEOCODE_INTERVAL_SECONDS = 1.0
_TIMEOUT_SECONDS = 15.0

JsonGetter = Callable[[str, dict[str, str]], Awaitable[Any]]


async def _get_json(url: str, params: dict[str, str]) -> Any:
    timeout = aiohttp.ClientTimeout(total=_TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(
        timeout=timeout,
        headers={"User-Agent": _USER_AGENT},
    ) as session:
        async with session.get(url, params=params) as response:
            response.raise_for_status()
            return await response.json()


class RoadDistanceCalculator:
    """Use public OpenStreetMap geocoding and OSRM driving-route services."""

    def __init__(self, json_get: JsonGetter = _get_json) -> None:
        self._json_get = json_get
        self._geocode_cache: dict[str, tuple[float, float] | None] = {}
        self._distance_cache: dict[str, float | None] = {}
        self._last_geocode_at: float | None = None

    async def from_commune_to_besancon(self, commune: str | None) -> float | None:
        """Return road distance in km between town centres, or None if either is unresolved."""
        if not isinstance(commune, str) or not commune.strip():
            return None

        normalized_commune = _normalize(commune)
        if not normalized_commune:
            return None
        if normalized_commune in self._distance_cache:
            return self._distance_cache[normalized_commune]

        origin = await self._geocode(_ORIGIN_QUERY)
        destination = await self._geocode(f"{commune.strip()}, France")
        if origin is None or destination is None:
            self._distance_cache[normalized_commune] = None
            logger.warning("Could not geocode Besançon or advertised commune %r.", commune)
            return None

        source_lat, source_lon = destination
        target_lat, target_lon = origin
        url = (
            f"{_ROUTER_URL}/"
            f"{source_lon},{source_lat};{target_lon},{target_lat}"
        )
        result = await self._json_get(
            url,
            {"overview": "false", "alternatives": "false", "steps": "false"},
        )
        distance = _route_distance_km(result)
        self._distance_cache[normalized_commune] = distance
        if distance is None:
            logger.warning("No driving route found for advertised commune %r.", commune)
        return distance

    async def _geocode(self, query: str) -> tuple[float, float] | None:
        cache_key = _normalize(query)
        if cache_key in self._geocode_cache:
            return self._geocode_cache[cache_key]

        if self._last_geocode_at is not None:
            elapsed = time.monotonic() - self._last_geocode_at
            wait_seconds = _MIN_GEOCODE_INTERVAL_SECONDS - elapsed
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)

        result = await self._json_get(
            _GEOCODER_URL,
            {
                "q": query,
                "format": "jsonv2",
                "limit": "1",
                "countrycodes": "fr",
            },
        )
        self._last_geocode_at = time.monotonic()
        coordinates = _geocode_coordinates(result)
        self._geocode_cache[cache_key] = coordinates
        return coordinates


def _geocode_coordinates(result: Any) -> tuple[float, float] | None:
    if not isinstance(result, list) or not result or not isinstance(result[0], dict):
        return None
    try:
        latitude = float(result[0]["lat"])
        longitude = float(result[0]["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None
    return latitude, longitude


def _route_distance_km(result: Any) -> float | None:
    if not isinstance(result, dict) or result.get("code") != "Ok":
        return None
    routes = result.get("routes")
    if not isinstance(routes, list) or not routes or not isinstance(routes[0], dict):
        return None
    distance_meters = routes[0].get("distance")
    if isinstance(distance_meters, bool) or not isinstance(distance_meters, (int, float)):
        return None
    if distance_meters < 0:
        return None
    return float(distance_meters) / 1000


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return " ".join(
        "".join(
            character
            for character in decomposed
            if not unicodedata.combining(character)
        ).split()
    )
