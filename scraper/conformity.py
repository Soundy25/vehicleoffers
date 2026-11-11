# Chemin exact : scraper/conformity.py [NEW]
"""Local read-only conformity evaluation used before any future GAS write."""

import re
import unicodedata
from typing import Any

from scraper.gas_client import GasVehicleCriteria


CONFORMING = "CONFORME"
NON_CONFORMING = "NON CONFORME"
NEEDS_REVIEW = "À VÉRIFIER"


def evaluate_vehicle_conformity(
    vehicle: dict[str, Any],
    criteria_rows: tuple[GasVehicleCriteria, ...],
    distance_km: float | None = None,
) -> tuple[str, tuple[str, ...]]:
    if not criteria_rows:
        raise ValueError("At least one vehicle criterion is required.")

    evaluations = [
        _evaluate_against_criteria(vehicle, criteria, distance_km)
        for criteria in criteria_rows
    ]
    for status in (CONFORMING,):
        matching = next((reasons for result, reasons in evaluations if result == status), None)
        if matching is not None:
            return status, matching
    unknown_reasons = tuple(
        dict.fromkeys(
            reason
            for status, reasons in evaluations
            if status == NEEDS_REVIEW
            for reason in reasons
        )
    )
    if unknown_reasons:
        return NEEDS_REVIEW, unknown_reasons
    return NON_CONFORMING, tuple(
        dict.fromkeys(reason for _, reasons in evaluations for reason in reasons)
    )


def _evaluate_against_criteria(
    vehicle: dict[str, Any],
    criteria: GasVehicleCriteria,
    distance_km: float | None,
) -> tuple[str, tuple[str, ...]]:
    title = _string(vehicle.get("title"))
    description = _string(vehicle.get("description"))
    searchable_text = f"{title} {description}"
    excluded = [term for term in criteria.exclusions if _contains(searchable_text, term)]
    if excluded:
        return NON_CONFORMING, ("Exclusion détectée : " + ", ".join(excluded),)

    reasons: list[str] = []
    missing: list[str] = []
    make = vehicle.get("make")
    if not make and _contains(title, criteria.brand):
        make = criteria.brand
    _check(
        "Marque",
        make,
        lambda value: _normalize(str(value)) == _normalize(criteria.brand),
        reasons,
        missing,
    )

    model = vehicle.get("model")
    if not model:
        model = next((item for item in criteria.models if _contains(title, item)), None)
    _check(
        "Modèle",
        model,
        lambda value: any(_normalize(str(value)) == _normalize(item) for item in criteria.models),
        reasons,
        missing,
    )

    _check_number("Prix", vehicle.get("price"), lambda value: value <= criteria.budget_max, reasons, missing)
    _check_number(
        "Kilométrage",
        vehicle.get("mileage"),
        lambda value: value <= criteria.mileage_max,
        reasons,
        missing,
    )
    _check_number("Année", vehicle.get("year"), lambda value: value >= criteria.year_min, reasons, missing)
    _check(
        "Énergie",
        vehicle.get("energy"),
        lambda value: _normalize(str(value)) == _normalize(criteria.energy)
        or (
            _normalize(criteria.energy) == "hybride"
            and _normalize(str(value)).startswith("hybride ")
        ),
        reasons,
        missing,
    )
    _check_number(
        "Nombre de places",
        vehicle.get("seats"),
        lambda value: value == criteria.seats,
        reasons,
        missing,
    )
    _check_number(
        "Distance",
        distance_km,
        lambda value: value <= criteria.distance_max_km,
        reasons,
        missing,
    )

    if reasons:
        return NON_CONFORMING, tuple(reasons)
    if missing:
        return NEEDS_REVIEW, tuple(f"{item} non renseigné" for item in missing)
    return CONFORMING, ("Tous les critères vérifiables sont respectés",)


def _check(
    label: str,
    actual: Any,
    predicate: Any,
    reasons: list[str],
    missing: list[str],
) -> None:
    if actual is None or actual == "":
        missing.append(label)
    elif not predicate(actual):
        reasons.append(f"{label} hors critère")


def _check_number(
    label: str,
    actual: Any,
    predicate: Any,
    reasons: list[str],
    missing: list[str],
) -> None:
    if actual is None or actual == "":
        missing.append(label)
        return
    try:
        number = float(actual)
    except (TypeError, ValueError):
        missing.append(label)
        return
    if not predicate(number):
        reasons.append(f"{label} hors critère")


def _contains(text: str, phrase: str) -> bool:
    normalized_text = f" {_normalize(text)} "
    normalized_phrase = _normalize(phrase)
    return bool(normalized_phrase) and f" {normalized_phrase} " in normalized_text


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.lower())
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", without_accents).split())


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""
