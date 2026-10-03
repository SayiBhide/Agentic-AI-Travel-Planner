import json
from pathlib import Path


DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "destinations.json"
)


def load_destinations() -> list[dict]:
    """
    Load the small curated destination knowledge base.

    This database is an optional local knowledge source.
    The travel planner is not restricted to these destinations.
    For destinations not present here, the web-search tool
    provides destination-specific information.
    """
    if not DATA_FILE.exists():
        return []

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def find_destinations(
    destination: str,
    interests: list[str] | None = None
) -> list[dict]:
    """
    Find locally curated places for a destination.

    The local database currently contains selected
    Mathura/Vrindavan demonstration places.

    If the requested destination is not present,
    an empty list is returned intentionally so that
    the agent can rely on web search instead.
    """

    destinations = load_destinations()

    destination_lower = destination.lower().strip()

    requested_cities = []

    # Combined demo destination
    if "mathura" in destination_lower:
        requested_cities.append("mathura")

    if "vrindavan" in destination_lower:
        requested_cities.append("vrindavan")

    # Check all database cities for other destinations
    if not requested_cities:
        for place in destinations:
            city = place.get("city", "").lower().strip()

            if city and city in destination_lower:
                requested_cities.append(city)

    matching = []

    for place in destinations:
        city = place.get("city", "").lower().strip()

        if city in requested_cities:
            matching.append(place)

    # Apply interest filtering when useful
    if interests and matching:

        interest_matches = []

        for place in matching:

            tags = [
                str(tag).lower().strip()
                for tag in place.get("tags", [])
            ]

            for interest in interests:
                if interest.lower().strip() in tags:
                    interest_matches.append(place)
                    break

        # Only replace the original result if
        # interest-based matches actually exist.
        if interest_matches:
            matching = interest_matches

    return matching

