# Chemin exact : tests/test_conformity.py [NEW]
import pytest

from scraper.conformity import CONFORMING, NEEDS_REVIEW, NON_CONFORMING, evaluate_vehicle_conformity
from scraper.gas_client import GasVehicleCriteria


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


@pytest.fixture
def compliant_vehicle() -> dict[str, object]:
    return {
        "title": "Toyota Yaris hybride",
        "make": "Toyota",
        "model": "Yaris",
        "price": 14_000,
        "mileage": 120_000,
        "year": 2020,
        "energy": "Hybride",
        "seats": 5,
        "description": "Carnet disponible",
    }


def test_inclusive_boundaries_classify_as_conforming(
    criteria: GasVehicleCriteria,
    compliant_vehicle: dict[str, object],
) -> None:
    status, reasons = evaluate_vehicle_conformity(
        compliant_vehicle,
        (criteria,),
        distance_km=350,
    )
    assert status == CONFORMING
    assert reasons == ("Tous les critères vérifiables sont respectés",)


def test_missing_distance_requires_review(
    criteria: GasVehicleCriteria,
    compliant_vehicle: dict[str, object],
) -> None:
    status, reasons = evaluate_vehicle_conformity(compliant_vehicle, (criteria,))
    assert status == NEEDS_REVIEW
    assert reasons == ("Distance non renseigné",)


def test_explicit_exclusion_is_non_conforming(
    criteria: GasVehicleCriteria,
    compliant_vehicle: dict[str, object],
) -> None:
    compliant_vehicle["description"] = "Véhicule accidenté"
    status, _ = evaluate_vehicle_conformity(compliant_vehicle, (criteria,), 100)
    assert status == NON_CONFORMING


def test_out_of_range_value_is_non_conforming(
    criteria: GasVehicleCriteria,
    compliant_vehicle: dict[str, object],
) -> None:
    compliant_vehicle["price"] = 14_001
    status, _ = evaluate_vehicle_conformity(compliant_vehicle, (criteria,), 100)
    assert status == NON_CONFORMING


def test_any_matching_criteria_row_can_conform(
    compliant_vehicle: dict[str, object],
) -> None:
    criteria = GasVehicleCriteria(
        brand="Honda",
        models=("Jazz",),
        budget_max=10_000,
        mileage_max=90_000,
        year_min=2022,
        energy="Essence",
        seats=2,
        distance_max_km=100,
        exclusions=(),
    )
    matching = GasVehicleCriteria(
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
    status, _ = evaluate_vehicle_conformity(
        compliant_vehicle,
        (criteria, matching),
        distance_km=200,
    )
    assert status == CONFORMING
