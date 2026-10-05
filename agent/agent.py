from __future__ import annotations

import json
import math
import re
import time
from typing import Any

from openai import OpenAI

from agent.constraints import check_constraints
from agent.state import AgentState
from tools.calculator import calculate
from tools.config import get_secret
from tools.destination_db import find_destinations
from tools.web_search import search_web


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_MODEL = "nvidia/nemotron-3.5-lightning:free"
DEFAULT_FALLBACK_MODELS = "qwen/qwen3.8-27b:free"
MAX_SEARCH_RESULTS = 20
MAX_REPLAN_ATTEMPTS = 1

COST_KEYS = [
    "transport_to_destination",
    "accommodation",
    "food",
    "local_transport",
    "activities",
    "miscellaneous",
]


# ============================================================
# BASIC HELPERS
# ============================================================

def _timeout() -> float:
    """Seconds to wait for one model reply. Slow 'thinking' models need a generous value."""
    try:
        return max(20.0, float(get_secret("OPENROUTER_TIMEOUT", "120") or 120))
    except ValueError:
        return 120.0


def _client() -> OpenAI:
    key = get_secret("OPENROUTER_API_KEY")

    if not key:
        raise ValueError(
            "OPENROUTER_API_KEY is not configured. On Streamlit Cloud add it in "
            "Manage app -> Settings -> Secrets. Locally use .streamlit/secrets.toml."
        )

    return OpenAI(
        api_key=key,
        base_url="https://openrouter.ai/api/v1",
        timeout=_timeout(),
        max_retries=1,
    )


def _models() -> list[str]:
    """Primary model first, then optional fallbacks (OPENROUTER_FALLBACK_MODELS=a,b,c)."""
    primary = get_secret("OPENROUTER_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL
    extra = get_secret("OPENROUTER_FALLBACK_MODELS", DEFAULT_FALLBACK_MODELS) or ""
    models = [primary] + [m.strip() for m in extra.split(",") if m.strip()]
    return list(dict.fromkeys(models))


def _trace(trace: list[dict[str, Any]], action: str, observation: Any) -> None:
    trace.append({"action": action, "observation": observation})


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _err(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"


class DailyLimitError(RuntimeError):
    """OpenRouter free-model daily quota is used up (account-wide, so other models won't help)."""


DAILY_LIMIT_MESSAGE = (
    "OpenRouter's daily free-model limit (50 requests/day) is used up. It resets at 00:00 UTC "
    "(5:30 AM IST). To remove this limit, add $10 of credits to your OpenRouter account "
    "(1,000 free-model requests per day)."
)


def _is_daily_limit(exc: Exception) -> bool:
    text = str(exc).lower()
    return "free-models-per-day" in text or "per-day" in text and "429" in text


def _llm(system: str, user: str, prefer: int = 0, diag: dict[str, Any] | None = None) -> str:
    """Call the models in order. `prefer` rotates the order so a retry can start with the backup model."""
    last_error: Exception | None = None

    models = _models()
    shift = prefer % len(models)
    ordered = models[shift:] + models[:shift]

    for model in ordered:
        try:
            response = _client().chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "detailed thinking off\n" + system},
                    {"role": "user", "content": user},
                ],
                temperature=0,
                max_tokens=6000,
            )
        except Exception as exc:
            if _is_daily_limit(exc):
                raise DailyLimitError(DAILY_LIMIT_MESSAGE) from exc

            last_error = exc
            continue

        if response.choices:
            choice = response.choices[0]
            text = _text(choice.message.content)

            if diag is not None:
                diag["model"] = model
                diag["finish_reason"] = getattr(choice, "finish_reason", None)

            if text:
                return text

    if last_error:
        raise last_error

    return ""


def _parse_json(text: str) -> dict[str, Any] | None:
    """Extract the plan JSON. Thinking models may write reasoning (with stray braces) first,
    so collect every JSON object in the text and prefer the one that looks like the plan."""
    if not text:
        return None

    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    candidates: list[dict[str, Any]] = []

    try:
        value = json.loads(cleaned)
        if isinstance(value, dict):
            candidates.append(value)
    except json.JSONDecodeError:
        pass

    if not candidates:
        decoder = json.JSONDecoder()
        position = 0

        while True:
            start = cleaned.find("{", position)

            if start == -1:
                break

            try:
                value, end = decoder.raw_decode(cleaned[start:])
            except json.JSONDecodeError:
                position = start + 1
                continue

            if isinstance(value, dict):
                candidates.append(value)

            position = start + max(end, 1)

    if not candidates:
        return None

    def score(candidate: dict[str, Any]) -> int:
        points = 0
        if isinstance(candidate.get("days"), list):
            points += 100 + len(candidate["days"])
        if isinstance(candidate.get("itinerary"), list):
            points += 90
        if "cost_breakdown" in candidate:
            points += 10
        return points

    return max(candidates, key=score)


def _calculate(expression: str) -> float:
    return round(float(calculate(expression)), 2)


# ============================================================
# TOOLS: TAVILY + LOCAL DATABASE
# ============================================================

def _web_search(
    destination: str,
    interests: list[str],
    start_location: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    interest_text = ", ".join(interests) if interests else "general sightseeing"

    place = destination if "india" in destination.lower() else f"{destination} India"

    queries = [
        f"{place} top attractions things to do {interest_text}",
        f"{place} famous places landmarks local food",
        (
            f"{place} budget travel cost hotel price per night food cost per day "
            f"local transport ticket prices rupees"
        ),
    ]

    if start_location:
        queries.append(
            f"{start_location} to {destination} train bus flight fare rupees"
        )

    results: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()

    for query in queries:
        try:
            items = search_web(query=query, max_results=5)
        except Exception as error:
            errors.append(_err(error))
            if "not configured" in str(error):
                break
            continue

        for item in items or []:
            title = _text(item.get("title"))
            url = _text(item.get("url"))
            content = _text(item.get("content"))[:500]

            key = url or title.lower()

            if not key or key in seen:
                continue

            seen.add(key)
            results.append({"title": title, "url": url, "content": content})

    return results[:MAX_SEARCH_RESULTS], list(dict.fromkeys(errors))


def _local_places(destination: str, interests: list[str], days: int) -> list[dict[str, Any]]:
    places = find_destinations(destination=destination, interests=interests)

    if not places:
        return []

    return places[: max(2, days * 3)]


# ============================================================
# ARTICLE-TITLE PROTECTION
# ============================================================

ARTICLE_PATTERNS = [
    "things to do",
    "travel guide",
    "travel itinerary",
    "best places",
    "top attractions",
    "where to stay",
    "where to eat",
    "must-see",
    "ultimate guide",
    "weekend guide",
    "tourist guide",
    "activities in",
    "day itinerary",
    "sites, attractions",
    "train from",
    "flight from",
    "bus from",
    "taxi from",
    "transfer from",
    "airport transfer",
    "rer b",
]


NOT_IN_INDIA_MESSAGE = (
    "TravelMind AI currently plans trips within India only (all costs are in ₹). "
    "Please enter an Indian destination such as Goa, Manali, Jaipur, Varanasi or Kerala."
)

FOREIGN_PLACES = [
    "paris", "london", "dubai", "abu dhabi", "singapore", "bangkok", "phuket", "pattaya", "bali",
    "tokyo", "kyoto", "osaka", "seoul", "new york", "los angeles", "las vegas", "san francisco",
    "toronto", "vancouver", "sydney", "melbourne", "rome", "venice", "milan", "barcelona", "madrid",
    "amsterdam", "berlin", "prague", "vienna", "zurich", "switzerland", "istanbul", "cairo",
    "maldives", "kathmandu", "nepal", "bhutan", "sri lanka", "colombo", "kuala lumpur", "malaysia",
    "thailand", "vietnam", "hong kong", "china", "japan", "usa", "united states", "uk",
    "united kingdom", "france", "italy", "spain", "germany", "australia", "canada", "europe",
]


def _obviously_foreign(destination: str) -> bool:
    text = destination.lower()
    return any(re.search(rf"\b{re.escape(place)}\b", text) for place in FOREIGN_PLACES)


PLACEHOLDER_NAMES = {
    "...", "..", ".", "-", "n/a", "na", "none", "null", "tbd", "name", "place", "attraction",
    "example", "sample", "real place", "real attraction", "place name", "attraction name",
}


def _is_placeholder(text: str) -> bool:
    value = text.lower().strip().strip(".:-*_ ")

    if not value:
        return True

    return (
        value in PLACEHOLDER_NAMES
        or value.startswith("real ")
        or value.startswith("name of")
        or value.startswith("<")
        or value.startswith("[")
    )


def _looks_like_article_title(name: str) -> bool:
    value = name.lower().strip()

    if _is_placeholder(value):
        return True

    if len(value) > 120:
        return True

    if value.startswith(("http://", "https://", "www.")):
        return True

    return any(pattern in value for pattern in ARTICLE_PATTERNS)


# ============================================================
# NORMALISATION / VALIDATION
# ============================================================

def _number(value: Any, default: float) -> float:
    try:
        return float(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        return default


def _activity(item: dict[str, Any], day: int, destination: str) -> dict[str, Any]:
    name = _text(item.get("name") or item.get("place") or item.get("attraction"))
    description = _text(item.get("description"))

    if _is_placeholder(description) or description.lower() in ("short", "short reason to visit"):
        description = ""

    category = _text(item.get("category")) or "Sightseeing"

    duration = _number(
        item.get("duration_hours", item.get("estimated_duration_hours", 2)), 2.0
    )
    fee = _number(item.get("estimated_entry_fee", item.get("entry_fee", 0)), 0.0)

    return {
        "day": int(day),
        "name": name,
        "city": _text(item.get("city")) or destination,
        "category": category,
        "description": description or f"Visit {name} in {destination}.",
        "entry_fee": round(max(0.0, fee), 2),
        "estimated_duration_hours": round(max(0.5, min(duration, 8.0)), 1),
    }


def _normalise_days(raw_days: Any, days: int, destination: str) -> list[dict[str, Any]]:
    if not isinstance(raw_days, list):
        return []

    grouped: dict[int, list[dict[str, Any]]] = {d: [] for d in range(1, days + 1)}

    for position, day_obj in enumerate(raw_days, start=1):
        if not isinstance(day_obj, dict):
            continue

        try:
            day = int(day_obj.get("day", position))
        except (TypeError, ValueError):
            day = position

        if day not in grouped:
            continue

        activities = (
            day_obj.get("activities")
            or day_obj.get("places")
            or day_obj.get("stops")
            or day_obj.get("items")
            or []
        )

        if not isinstance(activities, list):
            continue

        for item in activities[:3]:
            if isinstance(item, str):
                item = {"name": item}

            if not isinstance(item, dict):
                continue

            name = _text(item.get("name") or item.get("place") or item.get("attraction"))

            if not name or _looks_like_article_title(name):
                continue

            grouped[day].append(_activity(item, day, destination))

    return [item for d in grouped for item in grouped[d]]


def _valid_itinerary(itinerary: list[dict[str, Any]], days: int) -> bool:
    if not itinerary:
        return False

    for day in range(1, days + 1):
        if not any(int(item.get("day", 0)) == day for item in itinerary):
            return False

    for item in itinerary:
        name = _text(item.get("name"))
        if not name or _looks_like_article_title(name):
            return False

    names = {_text(i.get("name")).lower() for i in itinerary}

    if len(itinerary) >= 2 and len(names) < 2:
        return False

    return True


# ============================================================
# PROMPTS
# ============================================================

PLANNER_SYSTEM = """
You are the planning engine of an Agentic AI travel planner.
This planner supports destinations WITHIN INDIA ONLY. The destination may be any city, town, region or
state in India - you are NOT restricted to the local database.
If the destination is NOT in India, return ONLY this JSON and nothing else: {"not_in_india": true}

You combine: user requirements, Tavily web research, optional curated data, reasoning,
cost estimation and constraint-aware planning.

PLACE RULES
- Search-result titles are SOURCES, never itinerary activities.
- NEVER output article titles ("Best Things to Do in Paris", "Paris Travel Guide"),
  URLs or website names as activities.
- Extract REAL named places (landmarks, museums, temples, parks, markets, beaches,
  neighbourhoods, famous food streets) from the research and your own knowledge.
- Do not invent fake attractions.

COST RULES
- All amounts are in Indian Rupees (INR), for ALL travelers combined.
- Use realistic INDIAN prices: trains (sleeper/3AC), state buses, domestic flights when the distance
  is large, auto-rickshaws/cabs/e-rickshaws locally, dharamshalas and budget/mid-range hotels,
  local thalis and street food, Indian monument entry fees (often cheaper for Indian citizens).
- The user's budget is a MAXIMUM, not a target. Do not pad costs to reach it,
  and do not make an expensive destination unrealistically cheap to fit it.
- Cover: transport to destination (from the starting location, when given),
  accommodation (nights = days - 1; share rooms, ~2 people per room),
  food, local transport, activities/entry fees, miscellaneous.
- Use the supplied cost research. Use rounded planning estimates, not fake exact prices.
- If the budget is genuinely too low, do NOT pretend it is feasible: build the most
  economical sensible plan and let the constraint checker report the shortfall.

ITINERARY RULES
- Activities are places or experiences to visit. NEVER list transport legs (train, taxi, flight,
  airport transfer) as activities - transport costs belong only in cost_breakdown.
- If Food is among the interests, EVERY day must include at least one named food stop (a famous
  local eatery, sweet shop, food market or food street). Prefer eateries and markets named in the
  research; if none is supported by the research, name the famous food street, market or area
  instead of inventing a business.
- The "summary" must describe the trip only. Do NOT mention budget feasibility or rupee amounts in it.
- Exactly the requested number of days; each day has 1-3 REAL activities.
- Match the traveler's interests, keep the route geographically logical, avoid repeats.

OUTPUT: return ONLY valid JSON in exactly this shape:
{
  "summary": "short personalised summary",
  "cost_breakdown": {
    "transport_to_destination": 0,
    "accommodation": 0,
    "food": 0,
    "local_transport": 0,
    "activities": 0,
    "miscellaneous": 0
  },
  "days": [
    {"day": 1, "activities": [
      {"name": "<name of a real place>", "description": "<one sentence on why to visit>",
       "category": "Sightseeing", "duration_hours": 2, "estimated_entry_fee": 0}
    ]}
  ]
}
"""


def _planner_prompt(
    destination: str,
    days: int,
    travelers: int,
    budget: float,
    interests: list[str],
    start_location: str,
    local: list[dict[str, Any]],
    web: list[dict[str, Any]],
    lean: bool,
    previous_cost: float,
    hint: str = "",
) -> str:
    interest_text = ", ".join(interests) if interests else "general sightseeing"

    if lean:
        reduce_by = max(0.0, previous_cost - budget)
        mode = (
            f"REPLANNING: the previous plan cost about INR {previous_cost:,.0f}, which exceeds "
            f"the maximum budget of INR {budget:,.0f} by about INR {reduce_by:,.0f}.\n"
            "Create a clearly cheaper alternative: free or low-cost attractions, parks, walking "
            "areas, public transport, affordable food, budget accommodation. "
            "Keep all requested days. If the budget is genuinely too low, the total may stay above "
            "it - do NOT fake feasibility."
        )
    else:
        mode = (
            "Create the best realistic itinerary with a sensible estimate for the destination. "
            "Do not try to spend the whole budget and do not minimise cost artificially."
        )

    local_context = json.dumps(local[:12], ensure_ascii=False) if local else "None"
    web_context = json.dumps(web[:14], ensure_ascii=False) if web else "No web results available."

    return f"""
USER REQUIREMENTS
Destination: {destination}
Days: {days}
Travelers: {travelers}
Maximum total budget: INR {budget:,.0f}
Interests: {interest_text}
Starting location: {start_location or "Not specified"}

PLANNING MODE
{mode}

LOCAL CURATED DATA (optional, does not restrict the destination)
{local_context}

TAVILY WEB RESEARCH (sources - extract real places from the content)
{web_context}

{hint}

CHECK BEFORE RESPONDING
1. Exactly {days} day objects, each with 1-3 real activities in/near {destination}.
2. Activities match: {interest_text}.
3. Costs are in INR for all {travelers} travelers combined.
4. No article titles, URLs or website names as activities.
Return ONLY JSON.
"""


# ============================================================
# ONE PLANNING STEP (with retries)
# ============================================================

MAX_PLAN_ATTEMPTS = 2

FOOD_WORDS = (
    "food", "eat", "sweet", "market", "restaurant", "thali", "street food", "street-food",
    "cafe", "café", "bakery", "lassi", "kachori", "peda", "chaat", "bazaar", "eatery",
    "dhaba", "mithai", "cuisine", "tasting", "breakfast", "lunch", "dinner", "brunch",
)


def _food_missing(itinerary: list[dict[str, Any]], days: int, interests: list[str]) -> bool:
    """True when Food is an interest but some day has no food stop."""
    if "food" not in [i.lower() for i in interests]:
        return False

    for day in range(1, days + 1):
        items = [i for i in itinerary if int(i.get("day", 0)) == day]

        has_food = any(
            "food" in _text(i.get("category")).lower()
            or any(w in f"{i.get('name', '')} {i.get('description', '')}".lower() for w in FOOD_WORDS)
            for i in items
        )

        if not has_food:
            return True

    return False


def _plan_once(
    *,
    destination: str,
    days: int,
    travelers: int,
    budget: float,
    interests: list[str],
    start_location: str,
    local: list[dict[str, Any]],
    web: list[dict[str, Any]],
    lean: bool,
    previous_cost: float = 0.0,
) -> tuple[list[dict[str, Any]], str, dict[str, float], str]:
    """Returns (itinerary, summary, breakdown, error_message)."""

    error = ""
    best: tuple[dict[str, Any], list[dict[str, Any]]] | None = None
    hint = ""

    for _attempt in range(MAX_PLAN_ATTEMPTS):
        prompt = _planner_prompt(
            destination, days, travelers, budget, interests,
            start_location, local, web, lean, previous_cost, hint,
        )

        raw = ""
        diag: dict[str, Any] = {}
        started = time.monotonic()

        try:
            raw = _llm(PLANNER_SYSTEM, prompt, _attempt, diag)
        except DailyLimitError as exc:
            error = str(exc)
            break
        except Exception as exc:
            error = _err(exc)
            continue

        elapsed = time.monotonic() - started

        parsed = _parse_json(raw) if raw else None

        if parsed and parsed.get("not_in_india") is True and not parsed.get("days"):
            return [], "", {}, "NOT_IN_INDIA"

        itinerary = _normalise_days(parsed.get("days") or parsed.get("itinerary"), days, destination) if parsed else []

        if parsed and _valid_itinerary(itinerary, days):
            if best is None:
                best = (parsed, itinerary)

            if not _food_missing(itinerary, days, interests):
                best = (parsed, itinerary)
                break

            # Don't spend another slow call (and another daily request) on a food retry
            # when this model is slow; the app will show a clear warning instead.
            if elapsed > 45:
                break

            hint = (
                "IMPORTANT: your previous attempt had a day without any food stop. "
                "Every day MUST include at least one named food stop (famous local eatery, "
                "sweet shop, food market or food street) because Food is a selected interest."
            )
            continue

        reason = "no valid itinerary JSON"

        if not raw:
            reason = "empty reply"
        elif diag.get("finish_reason") == "length":
            reason = "reply was cut off before the JSON finished (model spent its token budget)"
        elif parsed and not itinerary:
            reason = "JSON found but no usable activities in it"
        elif parsed and itinerary:
            reason = "some days had no valid activities"

        error = (
            f"The model returned an unusable response ({reason}; model={diag.get('model')}, "
            f"finish_reason={diag.get('finish_reason')}, reply_start={raw[:150]!r})"
        )

    if best is None:
        return [], "", {}, error or "The model returned no usable itinerary."

    parsed, itinerary = best

    raw_breakdown = parsed.get("cost_breakdown", {})

    if not isinstance(raw_breakdown, dict):
        raw_breakdown = {}

    breakdown = {key: max(0.0, _number(raw_breakdown.get(key), 0.0)) for key in COST_KEYS}

    return itinerary, _text(parsed.get("summary")), breakdown, ""


# ============================================================
# OFFLINE FALLBACK (only used if the LLM is unavailable)
# ============================================================

def _local_fallback(destination: str, days: int, local: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean = [
        place for place in local
        if _text(place.get("name")) and not _looks_like_article_title(_text(place.get("name")))
    ]

    if not clean:
        return []

    result = [
        _activity(place, (index % days) + 1, destination)
        for index, place in enumerate(clean)
    ]

    for day in range(1, days + 1):
        if not any(item["day"] == day for item in result):
            result.append(_activity(clean[(day - 1) % len(clean)], day, destination))

    return result


# ============================================================
# COSTS
# ============================================================

def _baseline_breakdown(days: int, travelers: int) -> dict[str, float]:
    """Rough ECONOMY estimate (Indian domestic style), used only when the LLM gave no costs."""
    nights = max(days - 1, 0)
    rooms = math.ceil(travelers / 2)

    return {
        "transport_to_destination": travelers * 500.0,
        "accommodation": rooms * nights * 800.0,
        "food": travelers * days * 300.0,
        "local_transport": travelers * days * 100.0,
        "activities": travelers * days * 50.0,
        "miscellaneous": travelers * days * 50.0,
    }


def _finalise_breakdown(
    raw: dict[str, float],
    itinerary: list[dict[str, Any]],
    days: int,
    travelers: int,
) -> tuple[dict[str, float], list[str]]:
    notes: list[str] = []

    clean = {key: max(0.0, _number(raw.get(key), 0.0)) for key in COST_KEYS}

    if sum(clean.values()) <= 0:
        clean = _baseline_breakdown(days, travelers)
        notes.append("rough_economy_baseline_used")
    else:
        nights = max(days - 1, 0)
        rooms = math.ceil(travelers / 2)

        # Sanity floors so the model cannot return absurdly low numbers.
        food_floor = travelers * days * 150.0
        stay_floor = rooms * nights * 400.0

        if clean["food"] < food_floor:
            clean["food"] = food_floor
            notes.append("food_floor_applied")

        if nights > 0 and clean["accommodation"] < stay_floor:
            clean["accommodation"] = stay_floor
            notes.append("accommodation_floor_applied")

    entry_total = sum(_number(item.get("entry_fee"), 0.0) for item in itinerary)

    if clean["activities"] < entry_total:
        clean["activities"] = entry_total

    return {key: round(value, 2) for key, value in clean.items()}, notes


def _sum_breakdown(breakdown: dict[str, float]) -> float:
    expression = " + ".join(str(round(v, 2)) for v in breakdown.values()) or "0"
    return _calculate(expression)


def _build_summary(
    destination: str,
    days: int,
    travelers: int,
    interests: list[str],
    itinerary: list[dict[str, Any]],
) -> str:
    """Built from the final itinerary so it can never mention places that are not in the plan."""
    names: list[str] = []

    for item in itinerary:
        name = _text(item.get("name"))
        if name and name not in names:
            names.append(name)

    shown = names[:4]

    if len(shown) > 1:
        places = ", ".join(shown[:-1]) + " and " + shown[-1]
    else:
        places = shown[0] if shown else destination

    if len(interests) > 1:
        focus_list = ", ".join(interests[:-1]) + " and " + interests[-1]
    else:
        focus_list = interests[0] if interests else ""

    focus = f", focused on {focus_list}" if focus_list else ""
    more = f" (plus {len(names) - 4} more)" if len(names) > 4 else ""

    return (
        f"A {days}-day plan for {travelers} traveler{'s' if travelers != 1 else ''} "
        f"in {destination}{focus}. Highlights include {places}{more}."
    )


# ============================================================
# FINAL TEXT
# ============================================================

def _format_answer(
    destination: str,
    days: int,
    travelers: int,
    budget: float,
    start_location: str,
    cost: float,
    itinerary: list[dict[str, Any]],
    summary: str,
    warning: str = "",
) -> str:
    lines = [
        f"## {destination} — {days}-Day Itinerary",
        "",
        summary or f"A personalised {days}-day plan for {destination}.",
        "",
        f"**Travelers:** {travelers}  ",
        f"**Budget:** ₹{budget:,.0f}  ",
        f"**Estimated total:** ₹{cost:,.0f}  ",
        f"**Starting location:** {start_location or 'Not specified'}",
    ]

    if warning:
        lines.extend(["", f"⚠️ **Budget note:** {warning}"])

    lines.extend(["", "### Trip plan", ""])

    for day in range(1, days + 1):
        lines.append(f"#### Day {day}")

        for item in (i for i in itinerary if int(i.get("day", 0)) == day):
            fee = float(item.get("entry_fee", 0) or 0)
            fee_text = f"; estimated entry fee ₹{fee:,.0f}" if fee > 0 else ""

            hours = float(item["estimated_duration_hours"])
            hours_text = f"{hours:g} hour" if hours == 1 else f"{hours:g} hours"

            lines.append(
                f"- **{item['name']}** — {item['description']} "
                f"({hours_text}{fee_text})"
            )

        lines.append("")

    lines.extend(
        [
            "### Planning note",
            "",
            "The itinerary uses destination-specific web research and LLM reasoning. "
            "Costs are rough planning estimates (INR, all travelers combined), not booking prices. "
            "Please verify details before booking.",
        ]
    )

    return "\n".join(lines)


# ============================================================
# MAIN AGENT
# ============================================================

def run_travel_agent(
    *,
    destination: str,
    days: int,
    travelers: int,
    budget: float,
    interests: list[str],
    start_location: str,
) -> dict[str, Any]:
    destination = destination.strip()
    days = int(days)
    travelers = int(travelers)
    budget = float(budget)
    interests = list(interests or [])
    start_location = (start_location or "").strip()

    if not destination:
        raise ValueError("Destination is required.")

    if days < 1 or travelers < 1 or budget <= 0:
        raise ValueError("Days, travelers and budget must be positive.")

    if _obviously_foreign(destination):
        raise ValueError(NOT_IN_INDIA_MESSAGE)

    state = AgentState(
        destination=destination,
        days=days,
        travelers=travelers,
        budget=budget,
        interests=interests,
        start_location=start_location,
        status="running",
    )

    trace: list[dict[str, Any]] = []
    warnings: list[str] = []

    # 1. Goal
    _trace(trace, "goal_received", {
        "destination": destination, "days": days, "travelers": travelers,
        "budget": budget, "interests": interests, "start_location": start_location,
    })

    # 2. Local knowledge
    local = _local_places(destination, interests, days)
    _trace(trace, "destination_database", {
        "places_found": len(local), "source": "optional curated knowledge base",
    })

    # 3. Tavily
    web, search_errors = _web_search(destination, interests, start_location)
    _trace(trace, "tavily_search", {"results": len(web), "errors": search_errors})

    if not web:
        detail = f" ({search_errors[0]})" if search_errors else ""
        warnings.append(
            "Web search returned no results" + detail + ". "
            "The plan relies on the AI model's own knowledge, so costs may be less accurate."
        )

    # 4. First LLM plan
    itinerary, summary, breakdown, llm_error = _plan_once(
        destination=destination, days=days, travelers=travelers, budget=budget,
        interests=interests, start_location=start_location,
        local=local, web=web, lean=False,
    )

    if llm_error == "NOT_IN_INDIA":
        raise ValueError(NOT_IN_INDIA_MESSAGE)

    if not itinerary:
        itinerary = _local_fallback(destination, days, local)

        if not itinerary:
            raise RuntimeError(
                "The AI planner could not produce an itinerary. "
                f"Reason: {llm_error}. "
                "Check OPENROUTER_API_KEY / OPENROUTER_MODEL in your secrets, or try again."
            )

        breakdown = {}
        warnings.append(
            f"The AI planner was unavailable ({llm_error}). "
            "Showing the curated offline places with a rough economy cost estimate."
        )

    # 5. Calculator
    breakdown, notes = _finalise_breakdown(breakdown, itinerary, days, travelers)
    total_cost = _sum_breakdown(breakdown)
    state.total_cost = total_cost

    if "rough_economy_baseline_used" in notes:
        warnings.append(
            "The model did not return usable costs, so a rough economy estimate was used."
        )

    _trace(trace, "calculator", {
        "cost_breakdown": breakdown, "calculated_total": total_cost,
        "currency": "INR", "adjustments": notes,
    })

    # 6. Constraint check
    constraints = check_constraints(
        days=days, budget=budget, total_cost=total_cost, itinerary=itinerary,
    )
    _trace(trace, "constraint_check", constraints)

    # 7. Replanning (only when a real constraint fails)
    if not constraints["overall"] and state.replan_count < MAX_REPLAN_ATTEMPTS:
        state.replan_count += 1

        _trace(trace, "replan", {
            "reason": "initial plan did not satisfy one or more constraints",
            "failed_constraints": [k for k, v in constraints.items() if v is False],
            "previous_cost": total_cost,
            "budget": budget,
            "replan_number": state.replan_count,
        })

        lean_itinerary, lean_summary, lean_breakdown, lean_error = _plan_once(
            destination=destination, days=days, travelers=travelers, budget=budget,
            interests=interests, start_location=start_location,
            local=local, web=web, lean=True, previous_cost=total_cost,
        )

        if lean_itinerary:
            itinerary = lean_itinerary
            summary = lean_summary or summary
            breakdown, _ = _finalise_breakdown(lean_breakdown, itinerary, days, travelers)
            total_cost = _sum_breakdown(breakdown)
            state.total_cost = total_cost

            _trace(trace, "calculator_after_replan", {
                "cost_breakdown": breakdown, "calculated_total": total_cost,
            })
        else:
            warnings.append(f"Replanning failed ({lean_error}); the first plan was kept.")

    # 8. Final validation
    state.itinerary = itinerary
    state.constraint_results = check_constraints(
        days=days, budget=budget, total_cost=total_cost, itinerary=itinerary,
    )
    _trace(trace, "constraint_check_after_replan", state.constraint_results)

    summary = _build_summary(destination, days, travelers, interests, itinerary)

    if _food_missing(itinerary, days, interests):
        warnings.append(
            "Food is one of your interests, but the AI did not include a dedicated food stop on "
            "every day. Tick 'Generate a fresh plan' to try again."
        )

    warning = ""

    if not state.constraint_results.get("budget", True):
        warning = (
            f"The realistic estimate (₹{total_cost:,.0f}) is above the requested "
            f"₹{budget:,.0f} budget. The agent reduced discretionary costs while replanning "
            "but did not pretend the budget was feasible."
        )

    final_answer = _format_answer(
        destination, days, travelers, budget, start_location,
        total_cost, itinerary, summary, warning,
    )

    _trace(trace, "itinerary_generated", {
        "destination": destination, "days": days,
        "activities": len(itinerary), "estimated_cost": total_cost,
    })

    state.status = (
        "completed" if state.constraint_results.get("overall")
        else "completed_with_constraint_warning"
    )

    _trace(trace, "completed", {"status": state.status, "replan_count": state.replan_count})

    return {
        "status": state.status,
        "inputs": {
            "destination": destination, "days": days, "travelers": travelers,
            "budget": budget, "interests": interests, "start_location": start_location,
        },
        "itinerary": itinerary,
        "estimated_cost": round(total_cost, 2),
        "cost_breakdown": breakdown,
        "constraint_results": state.constraint_results,
        "replan_count": state.replan_count,
        "warnings": warnings,
        "final_answer": final_answer,
        "trace": trace,
    }

