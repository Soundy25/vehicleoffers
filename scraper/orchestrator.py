# Chemin exact : scraper/orchestrator.py
# Chemin exact : scraper/orchestrator.py [MODIFIÉ]
"""Read-only daily vehicle refresh orchestration for L'Argus."""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Callable, Protocol
from urllib.parse import urlsplit

from parsers.vehicle_parser import VehicleParser
from scraper.browser_engine import BrowserVisit, visit_once
from scraper.conformity import evaluate_vehicle_conformity
from scraper.gas_client import GasConfiguration, GasWebAppClient
from scraper.listing_parser import select_detail_candidates
from scraper.road_distance import RoadDistanceCalculator

logger = logging.getLogger(__name__)

MAX_DETAIL_VISITS_PER_REFRESH = 3
SUPPORTED_SEARCH_HOST = "occasion.largus.fr"


@dataclass(frozen=True)
class EvaluatedListing:
    url: str
    status: str
    reasons: tuple[str, ...]
    data: dict[str, object]


@dataclass(frozen=True)
class RefreshReport:
    search_url: str
    candidate_count: int
    skipped_count: int
    detail_visits: int
    limited: bool
    listings: tuple[EvaluatedListing, ...]


class ConfigurationProvider(Protocol):
    async def fetch_config(self) -> GasConfiguration: ...


class RoadDistanceProvider(Protocol):
    async def from_commune_to_besancon(self, commune: str | None) -> float | None: ...


class PipelineOrchestrator:
    def __init__(
        self,
        gas_client: ConfigurationProvider,
        browser_visit: Callable[[str], BrowserVisit] = visit_once,
        max_detail_visits: int = MAX_DETAIL_VISITS_PER_REFRESH,
        distance_calculator: RoadDistanceProvider | None = None,
    ) -> None:
        if not 1 <= max_detail_visits <= MAX_DETAIL_VISITS_PER_REFRESH:
            raise ValueError(
                f"max_detail_visits must be between 1 and {MAX_DETAIL_VISITS_PER_REFRESH}."
            )
        self.gas_client = gas_client
        self.browser_visit = browser_visit
        self.max_detail_visits = max_detail_visits
        self.distance_calculator = distance_calculator or RoadDistanceCalculator()
        self.report: RefreshReport | None = None

    @classmethod
    def from_environment(cls) -> "PipelineOrchestrator":
        web_app_url = os.environ.get("GAS_WEB_APP_URL")
        api_secret = os.environ.get("API_SECRET")
        hmac_secret = os.environ.get("HMAC_SECRET")
        missing = [
            name for name, value in (
                ("GAS_WEB_APP_URL", web_app_url),
                ("API_SECRET", api_secret),
            ) if not value
        ]
        if missing:
            raise RuntimeError("Missing required environment variables: " + ", ".join(missing))
        return cls(
            GasWebAppClient(
                web_app_url=web_app_url or "",
                api_secret=api_secret or "",
                hmac_secret=hmac_secret or "",
            )
        )

    def run(self) -> bool:
        config = asyncio.run(self.gas_client.fetch_config())
        self.report = self._run_read_only(config)
        return self.report is not None and not self.report.limited

    def _run_read_only(self, config: GasConfiguration) -> RefreshReport | None:
        search_url = next(
            (
                target for target in config.targets
                if urlsplit(target).hostname == SUPPORTED_SEARCH_HOST
            ),
            None,
        )
        if search_url is None:
            logger.error("No supported L'Argus search URL was returned by GAS.")
            return None

        search_visit = self.browser_visit(search_url)
        if search_visit.access_limited or not search_visit.html:
            logger.warning("Search page was unavailable or access-limited; stopping refresh.")
            return RefreshReport(search_url, 0, 0, 1, True, ())

        decisions = select_detail_candidates(
            search_visit.html,
            search_url,
            config.keys,
            config.criteria,
        )
        selected = [item for item in decisions if item.should_visit_detail]
        skipped_count = len(decisions) - len(selected)
        detail_results: list[EvaluatedListing] = []
        detail_visits = 0
        limited = False

        for decision in selected[:self.max_detail_visits]:
            detail_visits += 1
            detail_visit = self.browser_visit(decision.candidate.url)
            if detail_visit.access_limited:
                logger.warning("Detail page was access-limited; stopping further visits.")
                limited = True
                break
            if not detail_visit.html:
                logger.warning("Detail page returned no HTML; skipping extraction.")
                continue

            parsed_vehicles = asyncio.run(VehicleParser(detail_visit.html).parse())
            if not parsed_vehicles:
                logger.warning("No structured vehicle data found on detail page.")
                continue
            vehicle = parsed_vehicles[0]
            merged: dict[str, object] = {
                key: value for key, value in vehicle.items()
                if value is not None
            }
            merged["url"] = vehicle.get("url") or decision.candidate.url
            for key, value in (
                ("title", decision.candidate.title),
                ("price", decision.candidate.price),
                ("mileage", decision.candidate.mileage),
                ("year", decision.candidate.year),
                ("energy", decision.candidate.energy),
                ("seats", decision.candidate.seats),
            ):
                if not merged.get(key) and value is not None:
                    merged[key] = value
            city = merged.get("city")
            distance_km = asyncio.run(
                self.distance_calculator.from_commune_to_besancon(
                    city if isinstance(city, str) else None
                )
            )
            if distance_km is not None:
                merged["distance_km"] = distance_km
            status, reasons = evaluate_vehicle_conformity(merged, config.criteria, distance_km)
            detail_results.append(
                EvaluatedListing(
                    url=decision.candidate.url,
                    status=status,
                    reasons=reasons,
                    data=merged,
                )
            )

        report = RefreshReport(
            search_url=search_url,
            candidate_count=len(selected),
            skipped_count=skipped_count,
            detail_visits=detail_visits,
            limited=limited,
            listings=tuple(detail_results),
        )
        logger.info(
            "Read-only refresh complete: %d candidate(s), %d detail visit(s), %d parsed listing(s).",
            report.candidate_count,
            report.detail_visits,
            len(report.listings),
        )
        return report