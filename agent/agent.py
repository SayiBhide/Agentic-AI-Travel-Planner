from __future__ import annotations

import json
import re
from typing import Any

import streamlit as st
from openai import OpenAI

from agent.state import AgentState
from agent.constraints import check_constraints
from tools.calculator import calculate
from tools.destination_db import find_destinations
from tools.web_search import search_web


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_MODEL = "openrouter/free"

MAX_SEARCH_RESULTS = 20
MAX_REPLAN_ATTEMPTS = 1


# ============================================================
# BASIC HELPERS
# ============================================================

def _client() -> OpenAI:
    key = st.secrets.get("OPENROUTER_API_KEY")

    if not key:
        raise ValueError(
            "OPENROUTER_API_KEY is not configured."
        )

    return OpenAI(
        api_key=key,
        base_url="https://openrouter.ai/api/v1",
    )


def _model() -> str:
    return st.secrets.get(
        "OPENROUTER_MODEL",
        DEFAULT_MODEL
    )


def _trace(
    trace: list[dict[str, Any]],
    action: str,
    observation: Any
) -> None:

    trace.append(
        {
            "action": action,
            "observation": observation,
        }
    )


def _text(value: Any) -> str:

    if value is None:
        return ""

    return str(value).strip()


# ============================================================
# LLM CALL
# ============================================================

def _llm(
    system: str,
    user: str
) -> str:

    response = _client().chat.completions.create(
        model=_model(),
        messages=[
            {
                "role": "system",
                "content": system,
            },
            {
                "role": "user",
                "content": user,
            },
        ],
        temperature=0.1,
    )

    if not response.choices:
        return ""

    return _text(
        response.choices[0].message.content
    )


# ============================================================
# ROBUST JSON PARSER
# ============================================================

def _parse_json(
    text: str
) -> dict[str, Any] | None:

    if not text:
        return None

    cleaned = text.strip()

    # Remove markdown JSON fences.
    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.I,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
    )

    # Normal JSON.
    try:

        value = json.loads(cleaned)

        if isinstance(value, dict):
            return value

    except json.JSONDecodeError:
        pass

    # Recover JSON object embedded inside normal text.
    decoder = json.JSONDecoder()

    for match in re.finditer(
        r"\{",
        cleaned
    ):

        try:

            value, _ = decoder.raw_decode(
                cleaned[match.start():]
            )

            if isinstance(value, dict):
                return value

        except json.JSONDecodeError:
            continue

    return None


# ============================================================
# CALCULATOR TOOL
# ============================================================

def _calculate(
    expression: str
) -> float:

    return round(
        float(
            calculate(expression)
        ),
        2,
    )


# ============================================================
# TAVILY WEB SEARCH
# ============================================================

def _web_search(
    destination: str,
    interests: list[str]
) -> list[dict[str, Any]]:

    interest_text = (
        ", ".join(interests)
        if interests
        else "general sightseeing"
    )

    queries = [

        # Attractions
        (
            f"{destination} official tourism "
            f"attractions landmarks things to do "
            f"{interest_text}"
        ),

        # Places and itinerary
        (
            f"{destination} best attractions museums "
            f"temples parks neighborhoods food areas "
            f"travel itinerary"
        ),

        # COST RESEARCH
        (
            f"{destination} travel costs "
            f"hotel accommodation per night "
            f"food per day local transport "
            f"attraction ticket prices"
        ),

        # Budget/midrange research
        (
            f"{destination} budget mid range travel cost "
            f"3 day 5 day 7 day itinerary prices"
        ),

        # Practical information
        (
            f"{destination} practical travel guide "
            f"opening hours attractions public transport"
        ),
    ]

    results: list[dict[str, Any]] = []

    seen: set[str] = set()

    for query in queries:

        try:

            search_results = search_web(
                query=query,
                max_results=5,
            )

        except Exception:

            continue

        for item in search_results:

            title = _text(
                item.get("title")
            )

            url = _text(
                item.get("url")
            )

            content = _text(
                item.get("content")
            )

            key = (
                url
                or title.lower()
            )

            if not key:
                continue

            if key in seen:
                continue

            seen.add(key)

            results.append(
                {
                    "title": title,
                    "url": url,
                    "content": content,
                }
            )

    return results[:MAX_SEARCH_RESULTS]


# ============================================================
# LOCAL DESTINATION DATABASE
# ============================================================

def _local_places(
    destination: str,
    interests: list[str],
    days: int,
) -> list[dict[str, Any]]:

    places = find_destinations(
        destination=destination,
        interests=interests,
    )

    if not places:
        return []

    return places[
        : max(2, days * 3)
    ]


# ============================================================
# ARTICLE TITLE PROTECTION
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
    "days in ",
    "day itinerary",
    "sites, attractions",
]


def _looks_like_article_title(
    name: str
) -> bool:

    value = name.lower().strip()

    if len(value) > 120:
        return True

    return any(
        pattern in value
        for pattern in ARTICLE_PATTERNS
    )


# ============================================================
# NORMALISE ACTIVITY
# ============================================================

def _activity(
    item: dict[str, Any],
    day: int,
    destination: str,
) -> dict[str, Any]:

    name = _text(
        item.get("name")
        or item.get("place")
        or item.get("attraction")
    )

    description = _text(
        item.get("description")
    )

    category = (
        _text(
            item.get("category")
        )
        or "Sightseeing"
    )

    try:

        duration = float(
            item.get(
                "duration_hours",
                item.get(
                    "estimated_duration_hours",
                    2,
                ),
            )
            or 2
        )

    except (
        TypeError,
        ValueError,
    ):

        duration = 2.0

    try:

        fee = float(
            item.get(
                "estimated_entry_fee",
                item.get(
                    "entry_fee",
                    0,
                ),
            )
            or 0
        )

    except (
        TypeError,
        ValueError,
    ):

        fee = 0.0

    return {

        "day": int(day),

        "name": name,

        "city": (
            _text(
                item.get("city")
            )
            or destination
        ),

        "category": category,

        "description": (
            description
            or f"Visit {name} in {destination}."
        ),

        "entry_fee": round(
            max(0.0, fee),
            2,
        ),

        "estimated_duration_hours": round(
            max(
                0.5,
                min(duration, 8.0)
            ),
            1,
        ),
    }


# ============================================================
# NORMALISE DAY STRUCTURE
# ============================================================

def _normalise_days(
    raw_days: Any,
    days: int,
    destination: str,
) -> list[dict[str, Any]]:

    if not isinstance(
        raw_days,
        list
    ):

        return []

    grouped = {
        day: []
        for day in range(
            1,
            days + 1
        )
    }

    for day_obj in raw_days:

        if not isinstance(
            day_obj,
            dict
        ):

            continue

        try:

            day = int(
                day_obj.get("day")
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

        if day not in grouped:
            continue

        activities = day_obj.get(
            "activities",
            []
        )

        if not isinstance(
            activities,
            list
        ):

            continue

        for item in activities[:3]:

            if not isinstance(
                item,
                dict
            ):

                continue

            name = _text(
                item.get("name")
                or item.get("place")
                or item.get("attraction")
            )

            # CRITICAL:
            # Never allow article titles.
            if (
                not name
                or _looks_like_article_title(name)
            ):

                continue

            grouped[day].append(
                _activity(
                    item,
                    day,
                    destination,
                )
            )

    return [
        item
        for day in grouped
        for item in grouped[day]
    ]


# ============================================================
# ITINERARY VALIDATION
# ============================================================

def _valid_itinerary(
    itinerary: list[dict[str, Any]],
    days: int,
) -> bool:

    if not itinerary:
        return False

    # Every requested day must exist.
    for day in range(
        1,
        days + 1
    ):

        if not any(
            int(item.get("day", 0))
            == day
            for item in itinerary
        ):

            return False

    # Every activity must have a real name.
    for item in itinerary:

        name = _text(
            item.get("name")
        )

        if not name:
            return False

        if _looks_like_article_title(
            name
        ):

            return False

    return True


# ============================================================
# MAIN PLANNER SYSTEM PROMPT
# ============================================================

PLANNER_SYSTEM = """

You are the planning engine of an Agentic AI travel planner.

The user may enter ANY real destination in the world.

The application is NOT restricted to the local JSON database.

Your job is to combine:

1. user requirements
2. Tavily web research
3. optional curated destination data
4. LLM reasoning
5. cost calculation
6. constraint checking
7. adaptive replanning

------------------------------------------------------------
CRITICAL PLACE RULE
------------------------------------------------------------

Tavily search results are SOURCES.

Search-result titles are NOT itinerary activities.

NEVER output:

"Best Things to Do in Paris"

"Paris Travel Guide"

"37 Things to Do in Paris"

"The Ultimate Paris Itinerary"

"Where to Eat in Paris"

as activities.

Instead extract actual REAL places from source content, such as:

Eiffel Tower
Louvre Museum
Montmartre
Musée d'Orsay
Notre-Dame Cathedral
Seine River

when supported by the research.

------------------------------------------------------------
COST ESTIMATION
------------------------------------------------------------

The user's budget is a MAXIMUM LIMIT.

It is NOT a spending target.

If the user gives:

Budget = ₹100,000

DO NOT automatically make the trip cost ₹100,000.

But also DO NOT artificially make an expensive destination
unrealistically cheap just to stay under the budget.

Estimate a realistic rough trip cost for the destination.

The estimate must consider:

1. transport to destination, when applicable
2. accommodation
3. food
4. local transport
5. attractions and activities
6. miscellaneous expenses

The cost is for ALL travelers combined.

Use the supplied Tavily travel-cost research.

Do not invent exact live prices.

Use sensible rounded planning estimates.

For international destinations, do not use Indian domestic
travel assumptions.

For a very low budget:

DO NOT lie that the trip is feasible.

Create the most economical reasonable plan and allow the
deterministic constraint checker to report that the budget
is insufficient.

For a high budget:

DO NOT spend the entire budget unnecessarily.

------------------------------------------------------------
ITINERARY
------------------------------------------------------------

Create exactly the requested number of days.

Every day must contain 1–3 REAL places or activities.

Do not repeat places unnecessarily.

Match the user's interests.

Consider the starting location.

Keep the route reasonably logical.

------------------------------------------------------------
OUTPUT
------------------------------------------------------------

Return ONLY valid JSON.

Use exactly this structure:

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
    {
      "day": 1,

      "activities": [
        {
          "name": "REAL attraction",
          "description": "short reason to visit",
          "category": "Sightseeing",
          "duration_hours": 2,
          "estimated_entry_fee": 0
        }
      ]
    }
  ]
}

Important:

- cost_breakdown is TOTAL for all travelers
- all values must be non-negative
- cost breakdown should represent the complete trip
- its components should add up to the total estimated cost
- do not use article titles as places
- do not return URLs as activities
- do not return website names as activities
- do not invent fake attractions
"""


# ============================================================
# BUILD PLANNER PROMPT
# ============================================================

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
) -> str:

    if lean:

        mode = """

The previous plan exceeded the user's maximum budget.

Create a lower-cost alternative.

Prefer:

- free attractions
- low-cost attractions
- public parks
- walking areas
- public transport
- affordable food
- sensible accommodation

However:

DO NOT fake feasibility.

If the budget is genuinely too low,
the final cost may remain above the budget.

Keep all requested days.
"""

    else:

        mode = """

Create the best realistic itinerary.

Do NOT try to spend the whole budget.

Do NOT minimise the cost artificially.

Use a sensible mid-range travel estimate for the destination.
"""

    local_context = json.dumps(
        local[:12],
        ensure_ascii=False,
        indent=2,
    )

    web_context = json.dumps(
        web[:20],
        ensure_ascii=False,
        indent=2,
    )

    return f"""

USER REQUIREMENTS
=================

Destination:
{destination}

Days:
{days}

Travelers:
{travelers}

Maximum total budget:
INR {budget:,.0f}

Interests:
{
    ", ".join(interests)
    if interests
    else "general sightseeing"
}

Starting location:
{
    start_location
    if start_location
    else "Not specified"
}


PLANNING MODE
=============

{mode}


LOCAL CURATED DATA
==================

This is optional supplementary knowledge.

It does NOT restrict the destination.

{local_context}


TAVILY WEB RESEARCH
===================

The following information was retrieved specifically
for this destination.

Use it as evidence.

IMPORTANT:

Search-result titles are sources.

Extract REAL places from the content.

Never copy article titles into the itinerary.

{web_context}


FINAL VALIDATION BEFORE RESPONSE
================================

Check all of these:

1. Exactly {days} day objects.

2. Every day has 1–3 REAL activities.

3. Every activity is actually related to:
   {destination}

4. Activities match:
   {
       ", ".join(interests)
       if interests
       else "general sightseeing"
   }

5. Cost is for ALL {travelers} travelers.

6. Cost includes realistic accommodation,
   food, transport, activities and miscellaneous expenses.

7. Cost is NOT automatically equal to:
   INR {budget:,.0f}

8. A high budget does not mean the agent must spend it.

9. A low budget does not justify fake prices.

10. Do not use article titles as activities.

Return ONLY JSON.
"""


# ============================================================
# REPAIR MODEL
# ============================================================

REPAIR_SYSTEM = """

You are a repair component for an Agentic AI travel planner.

A previous LLM response may have:

- malformed JSON
- article titles as attractions
- missing days
- invalid activities
- missing cost breakdown

Repair the response.

Return ONLY valid JSON.

Use this schema:

{
  "summary": "...",

  "cost_breakdown": {
    "transport_to_destination": 0,
    "accommodation": 0,
    "food": 0,
    "local_transport": 0,
    "activities": 0,
    "miscellaneous": 0
  },

  "days": [
    {
      "day": 1,
      "activities": [
        {
          "name": "REAL place",
          "description": "...",
          "category": "Sightseeing",
          "duration_hours": 2,
          "estimated_entry_fee": 0
        }
      ]
    }
  ]
}

Rules:

- preserve real attraction names
- remove article titles
- remove URLs
- remove website names
- do not invent fake attractions
- exactly the requested number of days
- cost is TOTAL for all travelers
- budget is a maximum constraint, not a spending target
"""


# ============================================================
# REPAIR PLAN
# ============================================================

def _repair_plan(
    raw: str,
    original_prompt: str,
    days: int,
    destination: str,
) -> dict[str, Any] | None:

    repair_prompt = f"""

Destination:
{destination}

Requested days:
{days}


ORIGINAL PLANNING INSTRUCTIONS
==============================

{original_prompt}


CANDIDATE OUTPUT
================

{raw[:18000]}


TASK
====

Repair the candidate output into the exact required JSON format.

Make sure every requested day contains real activities.

Return ONLY JSON.
"""

    try:

        repaired = _llm(
            REPAIR_SYSTEM,
            repair_prompt,
        )

        return _parse_json(
            repaired
        )

    except Exception:

        return None


# ============================================================
# PLAN ONCE
# ============================================================

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
) -> tuple[
    list[dict[str, Any]],
    str,
    dict[str, float]
]:

    prompt = _planner_prompt(
        destination=destination,
        days=days,
        travelers=travelers,
        budget=budget,
        interests=interests,
        start_location=start_location,
        local=local,
        web=web,
        lean=lean,
    )

    raw = ""

    # First LLM attempt.
    try:

        raw = _llm(
            PLANNER_SYSTEM,
            prompt,
        )

    except Exception:

        raw = ""

    parsed = (
        _parse_json(raw)
        if raw
        else None
    )

    # Validate first response.
    itinerary = []

    if parsed:

        itinerary = _normalise_days(
            parsed.get("days"),
            days,
            destination,
        )

    # If invalid, ask the repair model.
    if not _valid_itinerary(
        itinerary,
        days,
    ):

        repaired = _repair_plan(
            raw
            or "No usable candidate output was returned.",
            prompt,
            days,
            destination,
        )

        if repaired:

            parsed = repaired

            itinerary = _normalise_days(
                parsed.get("days"),
                days,
                destination,
            )

    # Still invalid.
    if not _valid_itinerary(
        itinerary,
        days,
    ):

        return [], "", {}

    summary = _text(
        parsed.get("summary")
    )

    raw_breakdown = parsed.get(
        "cost_breakdown",
        {}
    )

    if not isinstance(
        raw_breakdown,
        dict
    ):

        raw_breakdown = {}

    keys = [

        "transport_to_destination",

        "accommodation",

        "food",

        "local_transport",

        "activities",

        "miscellaneous",

    ]

    breakdown: dict[str, float] = {}

    for key in keys:

        try:

            breakdown[key] = max(
                0.0,
                float(
                    raw_breakdown.get(
                        key,
                        0
                    )
                    or 0
                ),
            )

        except (
            TypeError,
            ValueError,
        ):

            breakdown[key] = 0.0

    return (
        itinerary,
        summary,
        breakdown,
    )


# ============================================================
# LOCAL FALLBACK
# ============================================================

def _local_fallback(
    destination: str,
    days: int,
    local: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    if not local:
        return []

    clean = [

        place

        for place in local

        if (
            _text(
                place.get("name")
            )
            and not _looks_like_article_title(
                _text(
                    place.get("name")
                )
            )
        )

    ]

    if not clean:
        return []

    result = []

    for index, place in enumerate(
        clean
    ):

        result.append(
            _activity(
                place,
                (index % days) + 1,
                destination,
            )
        )

    # Ensure every day has something.
    for day in range(
        1,
        days + 1
    ):

        if not any(
            item["day"] == day
            for item in result
        ):

            result.append(
                _activity(
                    clean[
                        (day - 1)
                        % len(clean)
                    ],
                    day,
                    destination,
                )
            )

    return result


# ============================================================
# COST BREAKDOWN CLEANING
# ============================================================

def _clean_breakdown(
    breakdown: dict[str, float],
    itinerary: list[dict[str, Any]],
) -> dict[str, float]:

    keys = [

        "transport_to_destination",

        "accommodation",

        "food",

        "local_transport",

        "activities",

        "miscellaneous",

    ]

    clean = {

        key: round(
            max(
                0.0,
                float(
                    breakdown.get(
                        key,
                        0
                    )
                ),
            ),
            2,
        )

        for key in keys

    }

    # Make sure known entry fees are not lost.
    entry_total = round(
        sum(
            float(
                item.get(
                    "entry_fee",
                    0
                )
                or 0
            )

            for item in itinerary
        ),
        2,
    )

    if (
        clean["activities"]
        < entry_total
    ):

        clean["activities"] = (
            entry_total
        )

    return clean


# ============================================================
# CALCULATE TOTAL
# ============================================================

def _sum_breakdown(
    breakdown: dict[str, float]
) -> float:

    expression = " + ".join(
        str(
            round(
                value,
                2
            )
        )

        for value in breakdown.values()
    )

    if not expression:
        expression = "0"

    return _calculate(
        expression
    )


# ============================================================
# FINAL ANSWER
# ============================================================

def _format_answer(
    destination: str,
    days: int,
    travelers: int,
    budget: float,
    start_location: str,
    cost: float,
    breakdown: dict[str, float],
    itinerary: list[dict[str, Any]],
    summary: str,
    warning: str = "",
) -> str:

    lines = [

        f"## {destination} — {days}-Day Itinerary",

        "",

        (
            summary
            or
            f"A personalised {days}-day plan for "
            f"{destination}."
        ),

        "",

        f"**Travelers:** {travelers}  ",

        f"**Budget:** ₹{budget:,.0f}  ",

        f"**Estimated total:** ₹{cost:,.0f}  ",

        (
            f"**Starting location:** "
            f"{start_location or 'Not specified'}"
        ),

        "",

        "### Estimated cost breakdown",

    ]

    labels = {

        "transport_to_destination":
            "Travel to destination",

        "accommodation":
            "Accommodation",

        "food":
            "Food",

        "local_transport":
            "Local transport",

        "activities":
            "Activities & entry fees",

        "miscellaneous":
            "Miscellaneous",

    }

    for key, label in labels.items():

        lines.append(
            f"- **{label}:** "
            f"₹{breakdown.get(key, 0):,.0f}"
        )

    if warning:

        lines.extend(
            [
                "",
                f"⚠️ **Budget note:** {warning}",
            ]
        )

    lines.extend(
        [
            "",
            "### Trip plan",
            "",
        ]
    )

    for day in range(
        1,
        days + 1
    ):

        lines.append(
            f"### Day {day}"
        )

        day_items = [

            item

            for item in itinerary

            if int(
                item.get(
                    "day",
                    0
                )
            ) == day

        ]

        for item in day_items:

            fee = float(
                item.get(
                    "entry_fee",
                    0
                )
                or 0
            )

            fee_text = (

                f"; estimated entry fee "
                f"₹{fee:,.0f}"

                if fee > 0

                else ""

            )

            lines.append(

                f"- **{item['name']}** — "
                f"{item['description']} "
                f"({item['estimated_duration_hours']:g} "
                f"hours{fee_text})"

            )

        lines.append("")

    lines.extend(
        [

            "### Planning note",

            "",

            "The itinerary uses destination-specific "
            "web research and LLM reasoning. The estimated "
            "cost is a rough planning estimate, not a "
            "guaranteed booking price.",

        ]
    )

    return "\n".join(
        lines
    )


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

    interests = list(
        interests or []
    )

    start_location = (
        start_location.strip()
    )

    # --------------------------------------------------------
    # INPUT VALIDATION
    # --------------------------------------------------------

    if not destination:

        raise ValueError(
            "Destination is required."
        )

    if (
        days < 1
        or travelers < 1
        or budget <= 0
    ):

        raise ValueError(
            "Days, travelers and budget "
            "must be positive."
        )

    # --------------------------------------------------------
    # STATE
    # --------------------------------------------------------

    state = AgentState(

        destination=destination,

        days=days,

        travelers=travelers,

        budget=budget,

        interests=interests,

        start_location=start_location,

        status="running",

    )

    trace: list[
        dict[str, Any]
    ] = []

    # --------------------------------------------------------
    # STEP 1: UNDERSTAND GOAL
    # --------------------------------------------------------

    _trace(

        trace,

        "goal_received",

        {

            "destination":
                destination,

            "days":
                days,

            "travelers":
                travelers,

            "budget":
                budget,

            "interests":
                interests,

            "start_location":
                start_location,

        },

    )

    # --------------------------------------------------------
    # STEP 2: LOCAL KNOWLEDGE TOOL
    # --------------------------------------------------------

    local = _local_places(

        destination,

        interests,

        days,

    )

    _trace(

        trace,

        "destination_database",

        {

            "places_found":
                len(local),

            "source":
                "optional curated knowledge base",

        },

    )

    # --------------------------------------------------------
    # STEP 3: TAVILY
    # --------------------------------------------------------

    try:

        web = _web_search(

            destination,

            interests,

        )

        _trace(

            trace,

            "tavily_search",

            {

                "results":
                    len(web),

                "queries":
                    5,

                "role":
                    "destination and cost research",

            },

        )

    except Exception as error:

        web = []

        _trace(

            trace,

            "tavily_search",

            {

                "status":
                    "unavailable",

                "message":
                    str(error),

            },

        )

    # --------------------------------------------------------
    # STEP 4: FIRST LLM PLAN
    # --------------------------------------------------------

    (
        itinerary,
        summary,
        breakdown,
    ) = _plan_once(

        destination=destination,

        days=days,

        travelers=travelers,

        budget=budget,

        interests=interests,

        start_location=start_location,

        local=local,

        web=web,

        lean=False,

    )

    # --------------------------------------------------------
    # LOCAL FALLBACK
    # --------------------------------------------------------

    if not itinerary:

        itinerary = _local_fallback(

            destination,

            days,

            local,

        )

        if itinerary:

            summary = (

                summary

                or

                f"A personalised {days}-day "
                f"plan for {destination}."

            )

            breakdown = {}

    # --------------------------------------------------------
    # NEVER USE WEB TITLES AS FALLBACK PLACES
    # --------------------------------------------------------

    if not itinerary:

        raise RuntimeError(

            "The AI planner did not return a valid "
            "itinerary after its repair attempt. "
            "Please retry the same trip. No fake "
            "or article-title activities were used."

        )

    # --------------------------------------------------------
    # STEP 5: CALCULATOR
    # --------------------------------------------------------

    breakdown = _clean_breakdown(

        breakdown,

        itinerary,

    )

    total_cost = _sum_breakdown(

        breakdown

    )

    state.total_cost = total_cost

    _trace(

        trace,

        "calculator",

        {

            "cost_breakdown":
                breakdown,

            "calculated_total":
                total_cost,

            "currency":
                "INR",

        },

    )

    # --------------------------------------------------------
    # STEP 6: CONSTRAINT CHECK
    # --------------------------------------------------------

    constraints = check_constraints(

        days=days,

        budget=budget,

        total_cost=total_cost,

        itinerary=itinerary,

    )

    _trace(

        trace,

        "constraint_check",

        constraints,

    )

    # --------------------------------------------------------
    # STEP 7: ADAPTIVE REPLANNING
    # --------------------------------------------------------

    if (

        not constraints["overall"]

        and

        state.replan_count
        < MAX_REPLAN_ATTEMPTS

    ):

        state.replan_count += 1

        failed = [

            key

            for key, value
            in constraints.items()

            if value is False

        ]

        _trace(

            trace,

            "replan",

            {

                "reason":
                    "initial plan did not satisfy "
                    "one or more constraints",

                "failed_constraints":
                    failed,

                "replan_number":
                    state.replan_count,

            },

        )

        (
            lean_itinerary,
            lean_summary,
            lean_breakdown,
        ) = _plan_once(

            destination=destination,

            days=days,

            travelers=travelers,

            budget=budget,

            interests=interests,

            start_location=start_location,

            local=local,

            web=web,

            lean=True,

        )

        if lean_itinerary:

            itinerary = (
                lean_itinerary
            )

            if lean_summary:

                summary = (
                    lean_summary
                )

            breakdown = _clean_breakdown(

                lean_breakdown,

                itinerary,

            )

            total_cost = _sum_breakdown(

                breakdown

            )

            state.total_cost = (
                total_cost
            )

            _trace(

                trace,

                "calculator_after_replan",

                {

                    "cost_breakdown":
                        breakdown,

                    "calculated_total":
                        total_cost,

                },

            )

    # --------------------------------------------------------
    # STEP 8: FINAL VALIDATION
    # --------------------------------------------------------

    state.itinerary = (
        itinerary
    )

    state.constraint_results = (
        check_constraints(

            days=days,

            budget=budget,

            total_cost=total_cost,

            itinerary=itinerary,

        )
    )

    _trace(

        trace,

        "constraint_check_after_replan",

        state.constraint_results,

    )

    # --------------------------------------------------------
    # BUDGET WARNING
    # --------------------------------------------------------

    warning = ""

    if not state.constraint_results.get(
        "budget",
        True
    ):

        warning = (

            f"The realistic estimate is above "
            f"the requested ₹{budget:,.0f} budget. "
            f"The agent reduced discretionary costs "
            f"during replanning, but it did not claim "
            f"that an unrealistic budget was feasible."

        )

    # --------------------------------------------------------
    # FINAL ANSWER
    # --------------------------------------------------------

    final_answer = _format_answer(

        destination=destination,

        days=days,

        travelers=travelers,

        budget=budget,

        start_location=start_location,

        cost=total_cost,

        breakdown=breakdown,

        itinerary=itinerary,

        summary=summary,

        warning=warning,

    )

    # --------------------------------------------------------
    # TRACE
    # --------------------------------------------------------

    _trace(

        trace,

        "itinerary_generated",

        {

            "destination":
                destination,

            "days":
                days,

            "activities":
                len(itinerary),

            "estimated_cost":
                total_cost,

        },

    )

    state.status = (

        "completed"

        if state.constraint_results.get(
            "overall"
        )

        else

        "completed_with_constraint_warning"

    )

    _trace(

        trace,

        "completed",

        {

            "status":
                state.status,

            "replan_count":
                state.replan_count,

        },

    )

    # --------------------------------------------------------
    # RETURN
    # --------------------------------------------------------

    return {

        "status":
            state.status,

        "itinerary":
            itinerary,

        "estimated_cost":
            round(
                total_cost,
                2
            ),

        "cost_breakdown":
            breakdown,

        "constraint_results":
            state.constraint_results,

        "replan_count":
            state.replan_count,

        "final_answer":
            final_answer,

        "trace":
            trace,

    }

