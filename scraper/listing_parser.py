# Chemin exact : scraper/listing_parser.py [NEW]
"""Extract visible listing-card facts and select detail-page candidates."""

from dataclasses import dataclass
import re
import unicodedata
from typing import Iterable
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from scraper.gas_client import GasVehicleCriteria


_ARGUS_DETAIL_PATH = re.compile(r"^/auto/annonce-[^/?#]+", re.IGNORECASE)
_PRICE = re.compile(r"(?<!\w)(\d[\d\s\u00a0\u202f.,]*)\s*€", re.IGNORECASE)
_MILEAGE = re.compile(r"(?<!\w)(\d[\d\s\u00a0\u202f.,]*)\s*km\b", re.IGNORECASE)
_YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
_SEATS = re.compile(r"(?<!\d)(\d{1,2})\s+places?\b", re.IGNORECASE)
_ENERGY_TERMS = (
    "hybride rechargeable",
    "hybride",
    "essence",
    "diesel",
    "électrique",
    "electrique",
    "gpl",
    "hydrogène",
    "hydrogene",
)


@dataclass(frozen=True)
class ListingCandidate:
    url: str
    title: str
    card_text: str
    price: float | None = None
    mileage: int | None = None
    year: int | None = None
    energy: str | None = None
    seats: int | None = None


@dataclass(frozen=True)
class CandidateDecision:
    candidate: ListingCandidate
    should_visit_detail: bool
    reasons: tuple[str, ...]


def parse_listing_candidates(html: str, search_url: str) -> list[ListingCandidate]:
    """Find same-site L'Argus detail links and facts explicitly visible in their cards."""
    search = urlsplit(search_url)
    if search.scheme != "https" or not search.hostname:
        raise ValueError("search_url must be an absolute HTTPS URL.")

    soup = BeautifulSoup(html, "html.parser")
    candidates: list[ListingCandidate] = []
    seen_urls: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = str(link.get("href", "")).strip()
        absolute_url = urljoin(search_url, href)
        parsed_url = urlsplit(absolute_url)
        if (
            parsed_url.scheme != "https"
            or parsed_url.hostname != search.hostname
            or not _ARGUS_DETAIL_PATH.match(parsed_url.path)
        ):
            continue
        url = _canonical_url(absolute_url)
        if url in seen_urls:
            continue
        seen_urls.add(url)

        card = _listing_card(link)
        card_text = " ".join(card.stripped_strings)
        title = _listing_title(link, card)
        candidates.append(
            ListingCandidate(
                url=url,
                title=title,
                card_text=card_text,
                price=_extract_amount(_PRICE, card_text),
                mileage=_extract_integer(_MILEAGE, card_text),
                year=_extract_year(card_text),
                energy=_extract_energy(card_text),
                seats=_extract_integer(_SEATS, card_text, group=1),
            )
        )
    return candidates


def prefilter_detail_candidates(
    candidates: Iterable[ListingCandidate],
    known_urls: Iterable[str],
    criteria: Iterable[GasVehicleCriteria],
) -> list[CandidateDecision]:
    """Discard known URLs and only listings proven incompatible by visible facts."""
    known = {_canonical_url(url) for url in known_urls}
    criterion_rows = tuple(criteria)
    if not criterion_rows:
        raise ValueError("At least one vehicle criterion is required.")

    decisions: list[CandidateDecision] = []
    for candidate in candidates:
        if _canonical_url(candidate.url) in known:
            continue
        per_criterion = [
            _incompatibilities(candidate, criterion) for criterion in criterion_rows
        ]
        if any(not reasons for reasons in per_criterion):
            decisions.append(
                CandidateDecision(
                    candidate=candidate,
                    should_visit_detail=True,
                    reasons=("No visible fact rules out every configured criterion",),
                )
            )
            continue
        reasons = tuple(dict.fromkeys(reason for row in per_criterion for reason in row))
        decisions.append(
            CandidateDecision(
                candidate=candidate,
                should_visit_detail=False,
                reasons=reasons,
            )
        )
    return decisions


def select_detail_candidates(
    html: str,
    search_url: str,
    known_urls: Iterable[str],
    criteria: Iterable[GasVehicleCriteria],
) -> list[CandidateDecision]:
    """Parse one results page, then return only unseen, not-proven-incompatible listings."""
    candidates = parse_listing_candidates(html, search_url)
    return prefilter_detail_candidates(candidates, known_urls, criteria)


def _incompatibilities(
    candidate: ListingCandidate,
    criteria: GasVehicleCriteria,
) -> tuple[str, ...]:
    text = _normalize(candidate.title + " " + candidate.card_text)
    reasons: list[str] = []

    excluded = [term for term in criteria.exclusions if _contains_phrase(text, term)]
    if excluded:
        return ("Explicit exclusion: " + ", ".join(excluded),)

    if candidate.price is not None and candidate.price > criteria.budget_max:
        reasons.append("Visible price exceeds maximum")
    if candidate.mileage is not None and candidate.mileage > criteria.mileage_max:
        reasons.append("Visible mileage exceeds maximum")
    if candidate.year is not None and candidate.year < criteria.year_min:
        reasons.append("Visible year is below minimum")
    if candidate.seats is not None and candidate.seats != criteria.seats:
        reasons.append("Visible seat count does not match")
    if candidate.energy is not None and not _same_energy(candidate.energy, criteria.energy):
        reasons.append("Visible energy type does not match")

    return tuple(reasons)


def _listing_card(link: Tag) -> Tag:
    for parent in link.parents:
        if not isinstance(parent, Tag):
            continue
        if parent.name in {"article", "li"} or parent.get("data-testid"):
            return parent
        if parent.name == "body":
            break
    return link.parent if isinstance(link.parent, Tag) else link


def _listing_title(link: Tag, card: Tag) -> str:
    heading = card.find(["h1", "h2", "h3", "h4"])
    if isinstance(heading, Tag):
        title = str(heading.get_text(" ", strip=True))
        if title:
            return title
    link_text = str(link.get_text(" ", strip=True))
    if link_text:
        return link_text
    image = link.find("img", alt=True)
    if isinstance(image, Tag):
        return str(image.get("alt", "")).strip()
    return ""


def _extract_amount(
    pattern: re.Pattern[str],
    text: str,
    group: int = 1,
) -> float | None:
    match = pattern.search(text)
    if not match:
        return None
    raw = match.group(group).replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
    raw = raw.replace(",", ".")
    if raw.count(".") > 1:
        raw = raw.replace(".", "")
    elif "." in raw and raw.split(".")[-1].isdigit() and len(raw.split(".")[-1]) == 3:
        raw = raw.replace(".", "")
    try:
        number = float(raw)
    except ValueError:
        return None
    return number


def _extract_integer(
    pattern: re.Pattern[str],
    text: str,
    group: int = 1,
) -> int | None:
    value = _extract_amount(pattern, text, group=group)
    if value is None or not value.is_integer():
        return None
    return int(value)


def _extract_year(text: str) -> int | None:
    years = [int(value) for value in _YEAR.findall(text)]
    return years[0] if years else None


def _extract_energy(text: str) -> str | None:
    normalized = _normalize(text)
    return next(
        (term for term in _ENERGY_TERMS if _contains_phrase(normalized, term)),
        None,
    )


def _same_energy(actual: str, expected: str) -> bool:
    normalized_actual = _normalize(actual)
    normalized_expected = _normalize(expected)
    return normalized_actual == normalized_expected or (
        normalized_expected == "hybride"
        and normalized_actual.startswith("hybride ")
    )


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized_text = " " + _normalize(text) + " "
    normalized_phrase = _normalize(phrase)
    return bool(normalized_phrase) and (" " + normalized_phrase + " ") in normalized_text


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.lower())
    without_accents = "".join(
        character for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(
        re.sub(r"[^a-z0-9]+", " ", without_accents.replace("œ", "oe"))
        .strip()
        .split()
    )


def _canonical_url(url: str) -> str:
    without_fragment, _ = urldefrag(url.strip())
    parsed = urlsplit(without_fragment)
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            "",
        )
    )
