# Chemin exact : tests/test_orchestrator.py [NEW]
import json

from scraper.browser_engine import BrowserVisit
from scraper.conformity import NEEDS_REVIEW
from scraper.gas_client import GasConfiguration, GasVehicleCriteria
from scraper.orchestrator import MAX_DETAIL_VISITS_PER_REFRESH, PipelineOrchestrator


class FakeGasClient:
    def __init__(self, config: GasConfiguration) -> None:
        self.config = config

    async def fetch_config(self) -> GasConfiguration:
        return self.config


class FakeDistanceCalculator:
    def __init__(self, distance_km: float | None = None) -> None:
        self.distance_km = distance_km
        self.communes: list[str | None] = []

    async def from_commune_to_besancon(self, commune: str | None) -> float | None:
        self.communes.append(commune)
        return self.distance_km


def _detail_html(title: str) -> str:
    return f"""
    <script type="application/ld+json">
    {json.dumps({
        "@context": "https://schema.org",
        "@type": "Car",
        "name": title,
        "brand": {"@type": "Brand", "name": "Toyota"},
        "model": "Yaris",
        "vehicleModelDate": "2021",
        "mileageFromOdometer": {"@type": "QuantitativeValue", "value": 50000},
        "fuelType": "Hybride",
        "vehicleSeatingCapacity": 5,
        "offers": {"@type": "Offer", "price": 13000},
    })}
    </script>
    """


def test_orchestrator_prefilters_and_visits_only_unseen_candidates() -> None:
    search_url = "https://occasion.largus.fr/auto/toyota/yaris/"
    known_url = "https://occasion.largus.fr/auto/annonce-known"
    over_budget_url = "https://occasion.largus.fr/auto/annonce-expensive"
    candidate_url = "https://occasion.largus.fr/auto/annonce-candidate"
    search_html = f"""
    <article><a href="{known_url}"><h2>Toyota Yaris</h2></a></article>
    <article><a href="{over_budget_url}"><h2>Toyota Yaris</h2><p>15 000 €</p></a></article>
    <article><a href="{candidate_url}"><h2>Toyota Yaris hybride</h2></a></article>
    """
    criteria = GasVehicleCriteria(
        brand="Toyota",
        models=("Yaris",),
        budget_max=14_000,
        mileage_max=120_000,
        year_min=2020,
        energy="Hybride",
        seats=5,
        distance_max_km=350,
        exclusions=("2 places", "véhicule accidenté"),
    )
    config = GasConfiguration(
        keys=(known_url,),
        targets=(search_url, "https://www.leboncoin.fr/recherche?category=2"),
        criteria=(criteria,),
    )
    visited: list[str] = []

    def browser_visit(url: str) -> BrowserVisit:
        visited.append(url)
        if url == search_url:
            return BrowserVisit(200, "Résultats", False, search_html)
        return BrowserVisit(200, "Détail", False, _detail_html("Toyota Yaris hybride"))

    orchestrator = PipelineOrchestrator(
        gas_client=FakeGasClient(config),
        browser_visit=browser_visit,
        distance_calculator=FakeDistanceCalculator(),
    )

    assert orchestrator.run() is True
    assert visited == [search_url, candidate_url]
    assert orchestrator.report is not None
    assert orchestrator.report.candidate_count == 1
    assert orchestrator.report.skipped_count == 1
    assert orchestrator.report.detail_visits == 1
    assert orchestrator.report.listings[0].status == NEEDS_REVIEW
    assert "Distance non renseigné" in orchestrator.report.listings[0].reasons


def test_orchestrator_stops_after_search_access_limitation() -> None:
    search_url = "https://occasion.largus.fr/auto/toyota/yaris/"
    criteria = GasVehicleCriteria(
        brand="Toyota",
        models=("Yaris",),
        budget_max=14_000,
        mileage_max=120_000,
        year_min=2020,
        energy="Hybride",
        seats=5,
        distance_max_km=350,
        exclusions=(),
    )
    config = GasConfiguration((), (search_url,), (criteria,))
    visited: list[str] = []

    def browser_visit(url: str) -> BrowserVisit:
        visited.append(url)
        return BrowserVisit(403, "", True)

    orchestrator = PipelineOrchestrator(
        gas_client=FakeGasClient(config),
        browser_visit=browser_visit,
    )

    assert orchestrator.run() is False
    assert visited == [search_url]
    assert orchestrator.report is not None
    assert orchestrator.report.limited is True
    assert orchestrator.report.detail_visits == 1


def test_orchestrator_caps_detail_visits() -> None:
    search_url = "https://occasion.largus.fr/auto/toyota/yaris/"
    candidate_urls = [
        f"https://occasion.largus.fr/auto/annonce-{index}"
        for index in range(MAX_DETAIL_VISITS_PER_REFRESH + 2)
    ]
    search_html = "".join(
        f'<article><a href="{url}"><h2>Toyota Yaris hybride</h2></a></article>'
        for url in candidate_urls
    )
    criteria = GasVehicleCriteria(
        brand="Toyota",
        models=("Yaris",),
        budget_max=14_000,
        mileage_max=120_000,
        year_min=2020,
        energy="Hybride",
        seats=5,
        distance_max_km=350,
        exclusions=(),
    )
    config = GasConfiguration((), (search_url,), (criteria,))
    visited: list[str] = []

    def browser_visit(url: str) -> BrowserVisit:
        visited.append(url)
        if url == search_url:
            return BrowserVisit(200, "Résultats", False, search_html)
        return BrowserVisit(200, "Détail", False, _detail_html("Toyota Yaris hybride"))

    orchestrator = PipelineOrchestrator(
        gas_client=FakeGasClient(config),
        browser_visit=browser_visit,
    )

    assert orchestrator.run() is True
    assert visited == [search_url, *candidate_urls[:MAX_DETAIL_VISITS_PER_REFRESH]]
    assert orchestrator.report is not None
    assert orchestrator.report.candidate_count == len(candidate_urls)
    assert orchestrator.report.detail_visits == MAX_DETAIL_VISITS_PER_REFRESH


def test_orchestrator_uses_road_distance_for_conformity() -> None:
    search_url = "https://occasion.largus.fr/auto/toyota/yaris/"
    candidate_url = "https://occasion.largus.fr/auto/annonce-distance"
    search_html = (
        f'<article><a href="{candidate_url}"><h2>Toyota Yaris hybride</h2></a></article>'
    )
    detail_data = json.loads(
        _detail_html("Toyota Yaris hybride")
        .split('<script type="application/ld+json">', 1)[1]
        .split("</script>", 1)[0]
    )
    detail_data["offers"]["seller"] = {
        "@type": "Organization",
        "name": "Vendeur",
        "address": {"@type": "PostalAddress", "addressLocality": "Dole"},
    }
    detail_html = (
        '<script type="application/ld+json">'
        + json.dumps(detail_data)
        + "</script>"
    )
    criteria = GasVehicleCriteria(
        brand="Toyota",
        models=("Yaris",),
        budget_max=14_000,
        mileage_max=120_000,
        year_min=2020,
        energy="Hybride",
        seats=5,
        distance_max_km=350,
        exclusions=(),
    )
    config = GasConfiguration((), (search_url,), (criteria,))

    def browser_visit(url: str) -> BrowserVisit:
        if url == search_url:
            return BrowserVisit(200, "Résultats", False, search_html)
        return BrowserVisit(200, "Détail", False, detail_html)

    distance_calculator = FakeDistanceCalculator(distance_km=45.2)
    orchestrator = PipelineOrchestrator(
        gas_client=FakeGasClient(config),
        browser_visit=browser_visit,
        distance_calculator=distance_calculator,
    )

    assert orchestrator.run() is True
    assert distance_calculator.communes == ["Dole"]
    assert orchestrator.report is not None
    listing = orchestrator.report.listings[0]
    assert listing.status == "CONFORME"
    assert listing.data["distance_km"] == 45.2
