# parsers/vehicle_parser.py
# Chemin exact : parsers/vehicle_parser.py [MODIFIÉ]
import json
import logging
from collections.abc import Iterator
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)

class VehicleParser(BaseParser):
    """Parse vehicle data from schema.org JSON-LD embedded in a detail page."""

    def __init__(self, html_content: str) -> None:
        super().__init__(html_content)
        self.soup: BeautifulSoup = BeautifulSoup(self.html_content, "html.parser")

    async def parse(self) -> List[Dict[str, Any]]:
        """Return validated vehicles found in JSON-LD; do not infer missing values."""
        results: List[Dict[str, Any]] = []
        for script in self.soup.select('script[type="application/ld+json"]'):
            try:
                document = json.loads(script.string or script.get_text())
            except json.JSONDecodeError:
                logger.warning("Ignoring malformed JSON-LD in vehicle page.")
                continue

            for candidate in _walk_dicts(document):
                if not _is_vehicle(candidate):
                    continue
                raw_data = _vehicle_fields(candidate)
                results.append(self.validate_and_clean(raw_data))

        if not results:
            logger.warning("No schema.org vehicle entity found in vehicle page.")
        return results


def _walk_dicts(value: Any) -> Iterator[Dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested_value in value.values():
            yield from _walk_dicts(nested_value)
    elif isinstance(value, list):
        for nested_value in value:
            yield from _walk_dicts(nested_value)


def _is_vehicle(value: Dict[str, Any]) -> bool:
    type_value = value.get("@type")
    types = type_value if isinstance(type_value, list) else [type_value]
    return any(
        isinstance(item, str) and item.rsplit("/", 1)[-1].lower() in {"car", "vehicle"}
        for item in types
    ) and isinstance(value.get("name"), str)


def _first_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, list):
        return next((item for item in value if isinstance(item, dict)), {})
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("value")
    return value


def _year(value: Any) -> Any:
    if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
        return int(value[:4])
    return value


def _text(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("name")
    if isinstance(value, list):
        return next((item for item in value if isinstance(item, str)), None)
    return value


def _vehicle_fields(vehicle: Dict[str, Any]) -> Dict[str, Any]:
    offers = _first_dict(vehicle.get("offers"))
    seller = _first_dict(offers.get("seller"))
    address = _first_dict(seller.get("address"))
    mileage = _number(vehicle.get("mileageFromOdometer"))
    brand = _text(vehicle.get("brand")) or _text(vehicle.get("manufacturer"))

    return {
        "title": vehicle["name"],
        "price": _number(offers.get("price")),
        "mileage": mileage,
        "year": _year(vehicle.get("vehicleModelDate") or vehicle.get("modelDate")),
        "city": address.get("addressLocality"),
        "seller": seller.get("name"),
        "make": brand,
        "model": _text(vehicle.get("model")),
        "energy": _text(vehicle.get("fuelType")),
        "seats": _number(vehicle.get("vehicleSeatingCapacity")),
        "description": vehicle.get("description"),
        "url": vehicle.get("url"),
    }