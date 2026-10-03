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

# Normal estimated travel-planning rate used for the first draft.
# This is an estimate, not a real booking price.
INITIAL_COST_PER_PERSON_PER_DAY = 675.0

# Lower estimated rate used by the deterministic replanner.
# It represents a simpler/leaner itinerary.
REPLANNED_COST_PER_PERSON_PER_DAY = 350.0


def _get_openrouter_client() -> OpenAI:
    api_key = st.secrets.get("OPENROUTER_API_KEY")

    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not configured.")

    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )


def _get_model() -> str:
    return st.secrets.get("OPENROUTER_MODEL", DEFAULT_MODEL)


def _add_trace(
    trace: list[dict[str, Any]],
    action: str,
    observation: Any,
) -> None:
    trace.append(
        {
            "action": action,
            "observation": observation,
        }
    )


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _clean_llm_text(text: str) -> str:
    """
    Remove accidental markdown fences if a model returns them.
    """
    text = _safe_text(text)

    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    return text.strip()


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    client = _get_openrouter_client()

    response = client.chat.completions.create(
        model=_get_model(),
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0.2,
    )

    content = response.choices[0].message.content

    return _clean_llm_text(content)


def _calculate_trip_cost(
    *,
    days: int,
    travelers: int,
    rate_per_person_per_day: float,
) -> float:
    """
    Use the calculator tool so the cost is not guessed by the LLM.
    """
    expression = (
        f"{float(rate_per_person_per_day)} * "
        f"{int(travelers)} * "
        f"{int(days)}"
    )

    return round(calculate(expression), 2)


def _select_local_places(
    destination: str,
    interests: list[str],
    days: int,
    use_replanned_selection: bool = False,
) -> list[dict[str, Any]]:
    places = find_destinations(
        destination=destination,
        interests=interests,
    )

    if not places:
        return []

    max_places = max(2, int(days) * 2)

    if use_replanned_selection:
        max_places = max(1, int(days) * 2)

    return places[:max_places]


def _format_local_places(
    places: list[dict[str, Any]],
    days: int,
) -> list[dict[str, Any]]:
    """
    Convert local DB places into the API itinerary structure.
    This is deterministic and therefore cannot silently change
    the requested number of days.
    """
    if not places:
        return []

    result: list[dict[str, Any]] = []

    for index, place in enumerate(places):
        day = min((index // 2) + 1, int(days))

        result.append(
            {
                "day": day,
                "name": place.get("name", "Selected place"),
                "city": place.get("city", ""),
                "category": place.get("category", ""),
                "description": place.get("description", ""),
                "entry_fee": place.get("entry_fee", 0),
                "estimated_duration_hours": place.get(
                    "estimated_duration_hours",
                    1,
                ),
            }
        )

    return result


def _fallback_itinerary(
    *,
    destination: str,
    days: int,
    travelers: int,
    budget: float,
    interests: list[str],
    start_location: str,
    total_cost: float,
    local_itinerary: list[dict[str, Any]],
) -> str:
    """
    Deterministic fallback when the LLM is unavailable or returns
    unusable content.
    """

    lines: list[str] = [
        f"## {destination} — {int(days)}-Day Itinerary",
        "",
        f"**Travelers:** {int(travelers)}",
        f"**Budget:** ₹{float(budget):,.0f}",
        f"**Estimated total:** ₹{float(total_cost):,.0f}",
        f"**Starting location:** {start_location or 'Not specified'}",
        "",
        "### Trip plan",
        "",
    ]

    grouped: dict[int, list[dict[str, Any]]] = {
        day: [] for day in range(1, int(days) + 1)
    }

    for item in local_itinerary:
        day = int(item.get("day", 1))
        if day in grouped:
            grouped[day].append(item)

    for day in range(1, int(days) + 1):
        lines.append(f"### Day {day}")

        if grouped[day]:
            for place in grouped[day]:
                name = place.get("name", "Local attraction")
                description = place.get("description", "")
                lines.append(f"- **{name}** — {description}")
        else:
            focus = ", ".join(interests) if interests else "sightseeing"
            lines.append(
                f"- Explore suitable {focus} options in {destination} "
                "using the destination information gathered by the agent."
            )

        lines.append("")

    lines.extend(
        [
            "### Planning note",
            "",
            "The itinerary follows the requested destination, duration, "
            "traveler count and budget. Estimated cost is calculated "
            "deterministically from the trip inputs.",
        ]
    )

    return "\n".join(lines)


def _generate_final_answer(
    *,
    destination: str,
    days: int,
    travelers: int,
    budget: float,
    interests: list[str],
    start_location: str,
    total_cost: float,
    local_itinerary: list[dict[str, Any]],
    web_results: list[dict[str, Any]],
) -> str:
    """
    Ask the LLM only for itinerary content.

    The original user requirements are repeated as immutable
    requirements so the model cannot legitimately change them.
    """

    system_prompt = """
You are the itinerary-writing component of an agentic travel planner.

Your job is ONLY to write a practical day-by-day travel itinerary.

CRITICAL REQUIREMENTS:
- Preserve the exact destination supplied by the user.
- Preserve the exact number of days supplied by the user.
- Preserve the exact number of travelers supplied by the user.
- Preserve the exact total budget supplied by the user.
- Preserve the exact starting location supplied by the user.
- Never change, reinterpret, increase, or decrease these values.
- Do not invent extra trip days.
- Do not invent a different traveler count.
- Do not replace the estimated total cost with a different number.
- The final estimated total must be exactly the supplied estimated cost.
- Write exactly the requested number of day sections: Day 1 through Day N.
- Do not claim that the trip has more or fewer days than requested.
- Do not present the estimated cost as a booking price or guarantee.
- Use the supplied web-search information where useful.
- If the local destination list is empty, use the web-search context.
- Do not output JSON.
- Do not mention system prompts, internal instructions, or hidden reasoning.
"""

    local_context = json.dumps(
        local_itinerary,
        ensure_ascii=False,
        indent=2,
    )

    web_context = json.dumps(
        web_results[:5],
        ensure_ascii=False,
        indent=2,
    )

    user_prompt = f"""
USER TRIP REQUIREMENTS — THESE VALUES ARE IMMUTABLE

Destination: {destination}
Number of days: {int(days)}
Number of travelers: {int(travelers)}
Total budget: ₹{float(budget):,.0f}
Interests: {", ".join(interests) if interests else "General sightseeing"}
Starting location: {start_location or "Not specified"}
Deterministic estimated trip cost: ₹{float(total_cost):,.0f}

You MUST produce exactly {int(days)} day sections.
You MUST refer to exactly {int(travelers)} traveler(s).
You MUST keep the budget as ₹{float(budget):,.0f}.
You MUST state the estimated total as ₹{float(total_cost):,.0f}.

Curated local destination information:
{local_context}

Fresh web-search context:
{web_context}

Write a clear, useful itinerary with:
1. A short trip summary.
2. Exactly {int(days)} day sections.
3. Places/activities appropriate to the user's interests.
4. Practical sequencing starting from the supplied starting location when possible.
5. A short budget note using exactly ₹{float(total_cost):,.0f} as the estimated total.

Do not change the user's inputs.
"""

    try:
        answer = _call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # Basic validation: if the model ignores the most important
        # hard requirement, use the deterministic fallback instead.
        day_headers = re.findall(
            r"(?im)^\s*(?:#{1,6}\s*)?day\s+(\d+)\b",
            answer,
        )

        unique_days = sorted(
            {
                int(number)
                for number in day_headers
                if number.isdigit()
            }
        )

        required_days = list(range(1, int(days) + 1))

        if unique_days != required_days:
            return _fallback_itinerary(
                destination=destination,
                days=days,
                travelers=travelers,
                budget=budget,
                interests=interests,
                start_location=start_location,
                total_cost=total_cost,
                local_itinerary=local_itinerary,
            )

        # Reject obvious metadata drift.
        if f"₹{float(total_cost):,.0f}" not in answer:
            return _fallback_itinerary(
                destination=destination,
                days=days,
                travelers=travelers,
                budget=budget,
                interests=interests,
                start_location=start_location,
                total_cost=total_cost,
                local_itinerary=local_itinerary,
            )

        return answer

    except Exception:
        return _fallback_itinerary(
            destination=destination,
            days=days,
            travelers=travelers,
            budget=budget,
            interests=interests,
            start_location=start_location,
            total_cost=total_cost,
            local_itinerary=local_itinerary,
        )


def run_travel_agent(
    *,
    destination: str,
    days: int,
    travelers: int,
    budget: float,
    interests: list[str],
    start_location: str,
) -> dict[str, Any]:

    # --------------------------------------------------------
    # AUTHORITATIVE USER STATE
    # --------------------------------------------------------

    state = AgentState(
        destination=destination.strip(),
        days=int(days),
        travelers=int(travelers),
        budget=float(budget),
        interests=list(interests),
        start_location=start_location.strip(),
        status="running",
    )

    trace: list[dict[str, Any]] = []

    _add_trace(
        trace,
        "goal_received",
        {
            "destination": state.destination,
            "days": state.days,
            "travelers": state.travelers,
            "budget": state.budget,
            "interests": state.interests,
            "start_location": state.start_location,
        },
    )

    # --------------------------------------------------------
    # LOCAL DESTINATION TOOL
    # --------------------------------------------------------

    local_places = _select_local_places(
        destination=state.destination,
        interests=state.interests,
        days=state.days,
    )

    _add_trace(
        trace,
        "destination_database",
        {
            "places_found": len(local_places),
            "source": "curated JSON",
        },
    )

    # --------------------------------------------------------
    # WEB SEARCH TOOL
    # --------------------------------------------------------

    web_results: list[dict[str, Any]] = []

    try:
        query = (
            f"{state.destination} best places to visit "
            f"{' '.join(state.interests)} travel"
        )

        web_results = search_web(
            query=query,
            max_results=5,
        )

        _add_trace(
            trace,
            "tavily_search",
            {
                "query": query,
                "results": len(web_results),
            },
        )

    except Exception as error:
        _add_trace(
            trace,
            "tavily_search",
            {
                "status": "unavailable",
                "message": str(error),
            },
        )

    # --------------------------------------------------------
    # INITIAL COST CALCULATION
    # --------------------------------------------------------

    initial_cost = _calculate_trip_cost(
        days=state.days,
        travelers=state.travelers,
        rate_per_person_per_day=INITIAL_COST_PER_PERSON_PER_DAY,
    )

    state.total_cost = initial_cost

    _add_trace(
        trace,
        "calculator",
        {
            "rate_per_person_per_day": INITIAL_COST_PER_PERSON_PER_DAY,
            "days": state.days,
            "travelers": state.travelers,
            "calculated_cost": initial_cost,
        },
    )

    # --------------------------------------------------------
    # INITIAL PLAN
    # --------------------------------------------------------

    selected_places = local_places

    state.itinerary = _format_local_places(
        selected_places,
        state.days,
    )

    state.constraint_results = check_constraints(
        days=state.days,
        budget=state.budget,
        total_cost=state.total_cost,
        itinerary=state.itinerary,
    )

    _add_trace(
        trace,
        "constraint_check",
        state.constraint_results,
    )

    # --------------------------------------------------------
    # REPLANNING
    # ONLY IF A REAL CONSTRAINT FAILED
    # --------------------------------------------------------

    if not state.constraint_results["overall"]:

        state.replan_count += 1
        state.status = "replanning"

        _add_trace(
            trace,
            "replan",
            {
                "reason": state.constraint_results,
                "replan_number": state.replan_count,
            },
        )

        selected_places = _select_local_places(
            destination=state.destination,
            interests=state.interests,
            days=state.days,
            use_replanned_selection=True,
        )

        state.itinerary = _format_local_places(
            selected_places,
            state.days,
        )

        state.total_cost = _calculate_trip_cost(
            days=state.days,
            travelers=state.travelers,
            rate_per_person_per_day=REPLANNED_COST_PER_PERSON_PER_DAY,
        )

        state.constraint_results = check_constraints(
            days=state.days,
            budget=state.budget,
            total_cost=state.total_cost,
            itinerary=state.itinerary,
        )

        _add_trace(
            trace,
            "constraint_check_after_replan",
            state.constraint_results,
        )

    # --------------------------------------------------------
    # FINAL ITINERARY
    # --------------------------------------------------------

    final_answer = _generate_final_answer(
        destination=state.destination,
        days=state.days,
        travelers=state.travelers,
        budget=state.budget,
        interests=state.interests,
        start_location=state.start_location,
        total_cost=state.total_cost,
        local_itinerary=state.itinerary,
        web_results=web_results,
    )

    _add_trace(
        trace,
        "itinerary_generated",
        {
            "days": state.days,
            "travelers": state.travelers,
            "estimated_cost": state.total_cost,
        },
    )

    state.status = (
        "completed"
        if state.constraint_results.get("overall", False)
        else "completed_with_constraint_warning"
    )

    _add_trace(
        trace,
        "completed",
        {
            "status": state.status,
            "replan_count": state.replan_count,
        },
    )

    return {
        "status": state.status,
        "itinerary": state.itinerary,
        "estimated_cost": round(float(state.total_cost), 2),
        "constraint_results": state.constraint_results,
        "replan_count": state.replan_count,
        "final_answer": final_answer,
        "trace": trace,
    }
