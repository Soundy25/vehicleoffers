# Chemin exact : tests/test_listing_parser.py [NEW]
import pytest

from scraper.gas_client import GasVehicleCriteria
from scraper.listing_parser import (
    ListingCandidate,
    parse_listing_candidates,
    prefilter_detail_candidates,
    select_detail_candidates,
)


@pytest.fixture
def criteria() -> GasVehicleCriteria:
    return GasVehicleCriteria(
        brand="Toyota",
        models=("Yaris", "Auris", "C-HR", "C-HR+"),
        budget_max=14_000,
        mileage_max=120_000,
        year_min=2020,
        energy="Hybride",
        seats=5,
        distance_max_km=350,
        exclusions=("2 places", "véhicule accidenté"),
    )


def test_parser_extracts_argus_detail_cards_and_visible_facts() -> None:
    html = """
    <article>
      <a href="/auto/annonce-abc-toyota-yaris">
        <h2>Toyota Yaris hybride</h2>
        <p>13 990 € · 96 000 km · 2021 · Hybride · 5 places</p>
      </a>
    </article>
    <a href="https://other.example/auto/annonce-ignored">Other site</a>
    <a href="/auto/annonce-duplicate#details">Duplicate</a>
    <a href="/auto/annonce-duplicate">Duplicate</a>
    <a href="/auto/annonce-query?tracking=1">Toyota Auris</a>
    """

    candidates = parse_listing_candidates(
        html,
        "https://occasion.largus.fr/auto/toyota/yaris/",
    )

    assert len(candidates) == 3
    assert candidates[0].url == "https://occasion.largus.fr/auto/annonce-abc-toyota-yaris"
    assert candidates[0].title == "Toyota Yaris hybride"
    assert candidates[0].price == 13990
    assert candidates[0].mileage == 96000
    assert candidates[0].year == 2021
    assert candidates[0].energy == "hybride"
    assert candidates[0].seats == 5


def test_prefilter_skips_known_urls_and_explicitly_incompatible_listings(
    criteria: GasVehicleCriteria,
) -> None:
    known = ListingCandidate(
        url="https://occasion.largus.fr/auto/annonce-known",
        title="Toyota Yaris",
        card_text="",
    )
    too_expensive = ListingCandidate(
        url="https://occasion.largus.fr/auto/annonce-expensive",
        title="Toyota Yaris",
        card_text="15 000 €",
        price=15000,
    )
    excluded = ListingCandidate(
        url="https://occasion.largus.fr/auto/annonce-accident",
        title="Toyota Yaris accidentée",
        card_text="Véhicule accidenté",
    )
    candidate = ListingCandidate(
        url="https://occasion.largus.fr/auto/annonce-candidate",
        title="Toyota Yaris hybride",
        card_text="2021",
        year=2021,
    )

    decisions = prefilter_detail_candidates(
        [known, too_expensive, excluded, candidate],
        ["https://occasion.largus.fr/auto/annonce-known/?utm_source=alert"],
        [criteria],
    )

    assert [item.candidate.url for item in decisions] == [
        too_expensive.url,
        excluded.url,
        candidate.url,
    ]
    assert [item.should_visit_detail for item in decisions] == [False, False, True]


def test_unknown_summary_fields_are_kept_for_detail_review(criteria: GasVehicleCriteria) -> None:
    candidate = ListingCandidate(
        url="https://occasion.largus.fr/auto/annonce-unknown",
        title="Toyota Yaris",
        card_text="",
    )

    decision = prefilter_detail_candidates([candidate], [], [criteria])[0]

    assert decision.should_visit_detail is True
    assert decision.reasons == ("No visible fact rules out every configured criterion",)


def test_any_matching_criterion_keeps_candidate() -> None:
    other_criteria = GasVehicleCriteria(
        brand="Honda",
        models=("Jazz",),
        budget_max=12_000,
        mileage_max=100_000,
        year_min=2019,
        energy="Hybride",
        seats=5,
        distance_max_km=300,
        exclusions=("accidenté",),
    )
    toyota_criteria = GasVehicleCriteria(
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
    candidate = ListingCandidate(
        url="https://occasion.largus.fr/auto/annonce-toyota",
        title="Toyota Yaris",
        card_text="",
        price=13_000,
    )

    decision = prefilter_detail_candidates(
        [candidate],
        [],
        [other_criteria, toyota_criteria],
    )[0]

    assert decision.should_visit_detail is True


def test_prefilter_requires_criteria() -> None:
    with pytest.raises(ValueError, match="At least one"):
        prefilter_detail_candidates([], [], [])


def test_parser_rejects_non_https_search_urls() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        parse_listing_candidates("", "http://occasion.largus.fr/search")


def test_select_detail_candidates_composes_parse_and_prefilter(
    criteria: GasVehicleCriteria,
) -> None:
    html = """
    <article>
      <a href="/auto/annonce-over-budget">
        <h2>Toyota Yaris</h2><p>15 000 €</p>
      </a>
    </article>
    <article>
      <a href="/auto/annonce-unknown">
        <h2>Toyota Yaris</h2>
      </a>
    </article>
    """

    decisions = select_detail_candidates(
        html,
        "https://occasion.largus.fr/auto/toyota/yaris/",
        [],
        [criteria],
    )

    assert [decision.should_visit_detail for decision in decisions] == [False, True]
