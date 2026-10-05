import math
import sys
from pathlib import Path

import streamlit as st

# ============================================================
# PROJECT ROOT (so `agent` and `tools` can be imported)
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.agent import run_travel_agent  # noqa: E402


# ============================================================
# PAGE CONFIG + CSS
# ============================================================

st.set_page_config(
    page_title="TravelMind AI",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .stApp { background-color: #FFF9F3; }
    .block-container { max-width: 1180px; padding-top: 2rem; padding-bottom: 4rem; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { background: transparent !important; }

    .hero-title-text { color:#12355B; font-size:46px; font-weight:850; line-height:1.05; margin:4px 0 8px 0; }
    .hero-subtitle-text { color:#536878; font-size:17px; line-height:1.65; max-width:850px; margin-bottom:8px; }
    .hero-note-text { color:#176B87; font-size:14px; font-weight:650; margin-bottom:20px; }
    .hero-badge-text { color:#176B87; font-size:12px; font-weight:800; letter-spacing:0.7px; margin-bottom:2px; }
    .section-title-text { color:#12355B; font-size:27px; font-weight:800; margin-top:24px; margin-bottom:3px; }
    .section-subtitle-text { color:#718096; font-size:14px; margin-bottom:15px; }

    .stButton > button { border-radius:13px; font-weight:750; min-height:46px; }
    .stButton > button[kind="primary"] { background: linear-gradient(90deg,#FF7A59,#FF9F68); border:none; }
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div { border-radius:11px; }

    div[data-testid="stMetric"] {
        background:white; border:1px solid #F0E4D8; border-radius:16px;
        padding:15px 17px; box-shadow:0 5px 16px rgba(40,70,90,0.05);
    }
    div[data-testid="stMetricLabel"] { color:#718096; }
    div[data-testid="stMetricValue"] { color:#12355B; }
    div[data-testid="stExpander"] { border:1px solid #E9DED3; border-radius:14px; background:white; }

    .footer-text { text-align:center; color:#8A98A5; font-size:12px; margin-top:42px;
                   padding-top:20px; border-top:1px solid #EDE2D8; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "result" not in st.session_state:
    st.session_state.result = None


@st.cache_resource
def _plan_cache() -> dict:
    """Server-wide memory of finished plans, so identical inputs give identical output."""
    return {}


def get_plan(destination, days, travelers, budget, interests, start_location, fresh):
    key = (
        destination.strip().lower(), int(days), int(travelers), float(budget),
        tuple(sorted(interests)), start_location.strip().lower(),
    )
    cache = _plan_cache()

    if not fresh and key in cache:
        return {**cache[key], "from_cache": True}

    result = run_travel_agent(
        destination=destination.strip(),
        days=int(days),
        travelers=int(travelers),
        budget=float(budget),
        interests=list(interests),
        start_location=start_location.strip(),
    )

    # Only remember clean results (never remember fallback/failed ones).
    if not result.get("warnings"):
        cache[key] = result

    return {**result, "from_cache": False}


def title(text: str) -> None:
    st.markdown(f'<div class="section-title-text">{text}</div>', unsafe_allow_html=True)


def subtitle(text: str) -> None:
    st.markdown(f'<div class="section-subtitle-text">{text}</div>', unsafe_allow_html=True)


# ============================================================
# HERO
# ============================================================

st.markdown('<div class="hero-badge-text">✨ AI-POWERED • TOOL-USING • ADAPTIVE</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title-text">🌴 TravelMind AI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-subtitle-text">Your intelligent travel planning agent that searches destination '
    'information, reasons over your requirements, calculates estimated costs and adapts the journey '
    'when constraints are not satisfied.</div>',
    unsafe_allow_html=True,
)
st.markdown('<div class="hero-note-text">🇮🇳 Plan trips to destinations across India • all costs in ₹</div>', unsafe_allow_html=True)
st.divider()


# ============================================================
# INPUTS
# ============================================================

title("Plan your journey")
subtitle("Tell the agent what kind of trip you want. Destinations within India are supported.")

left, right = st.columns(2)

with left:
    destination = st.text_input(
        "📍 Destination",
        value="Mathura & Vrindavan",
        placeholder="Goa, Manali, Jaipur, Varanasi, Kerala...",
    )
    start_location = st.text_input(
        "🚉 Starting location",
        value="Mathura Railway Station",
        placeholder="City, railway station or airport in India",
    )
    days = st.number_input("🗓️ Number of days", min_value=1, max_value=30, value=2, step=1)

with right:
    travelers = st.number_input("👥 Number of travelers", min_value=1, max_value=100, value=4, step=1)
    budget = st.number_input(
        "💰 Total trip budget (₹)", min_value=100, max_value=100000000, value=5000, step=500
    )

    interest_options = {
        "🛕 Temples & Culture": "temples",
        "🍜 Food": "food",
        "🏛️ Heritage": "heritage",
        "🌿 Nature": "nature",
        "🛍️ Shopping": "shopping",
        "🏖️ Beaches": "beaches",
        "🏔️ Adventure": "adventure",
        "🌙 Nightlife": "nightlife",
        "🧘 Relaxation": "relaxation",
        "📸 Sightseeing": "sightseeing",
    }

    selected_labels = st.multiselect(
        "❤️ Travel interests",
        options=list(interest_options.keys()),
        default=["🛕 Temples & Culture", "🍜 Food"],
    )

    interests = [interest_options[label] for label in selected_labels]

_, button_col, _ = st.columns([1, 2, 1])

with button_col:
    plan_trip = st.button("✈️ Plan My Journey", use_container_width=True, type="primary")
    fresh_plan = st.checkbox(
        "🔄 Generate a fresh plan (ignore the saved plan for these inputs)", value=False
    )


# ============================================================
# INTRO (before first plan)
# ============================================================

if st.session_state.result is None and not plan_trip:
    st.info(
        "🤖 **How TravelMind AI works**\n\n"
        "TravelMind AI does more than generate a fixed itinerary. The agent understands the trip "
        "requirements, gathers information using external tools, estimates costs, checks constraints "
        "and can revise its plan when the initial plan does not satisfy them."
    )
    st.success(
        "💡 **Agentic example:** If the initial plan exceeds the requested budget, the agent triggers "
        "a replanning step and generates a cheaper plan."
    )


# ============================================================
# RUN THE AGENT
# ============================================================

if plan_trip:
    if not destination.strip():
        st.error("Please enter a destination.")
    elif not selected_labels:
        st.error("Please select at least one travel interest.")
    else:
        with st.spinner("🤖 Your travel agent is searching, calculating and planning... (this can take up to a minute)"):
            try:
                st.session_state.result = get_plan(
                    destination, days, travelers, budget, interests, start_location, fresh_plan
                )
                st.rerun()
            except Exception as error:
                st.error("The travel agent could not complete the request.")
                st.code(f"{type(error).__name__}: {error}")


# ============================================================
# RESULTS
# ============================================================

result = st.session_state.result

if result is not None:
    # Always use the inputs the plan was generated with (not the current widget values).
    inp = result.get("inputs", {})
    r_dest = inp.get("destination", destination)
    r_days = int(inp.get("days", days))
    r_budget = float(inp.get("budget", budget))

    estimated_cost = float(result.get("estimated_cost", 0))
    replan_count = int(result.get("replan_count", 0))
    constraints = result.get("constraint_results", {})
    breakdown = result.get("cost_breakdown", {}) or {}

    _, new_col = st.columns([5, 1])

    with new_col:
        if st.button("↻ New Trip", use_container_width=True):
            st.session_state.result = None
            st.rerun()

    if result.get("from_cache"):
        st.info(
            "ℹ️ Showing the saved plan for these exact inputs. "
            "Tick 'Generate a fresh plan' to create a new one."
        )

    for message in result.get("warnings", []):
        st.warning(message)

    if constraints.get("overall"):
        st.success(f"✓ Journey planned successfully for **{r_dest}**. The agent completed its planning and validation process.")
    else:
        st.warning(f"⚠ Journey planned for **{r_dest}**, but one or more constraints are not fully satisfied (see validation below).")

    # ---------------- summary ----------------
    title("Your AI-planned journey")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📍 Destination", r_dest)
    m2.metric("🗓️ Duration", f"{r_days} day{'s' if r_days != 1 else ''}")
    m3.metric("💰 Estimated cost", f"₹{estimated_cost:,.0f}")
    m4.metric("🔄 AI replans", replan_count)

    # ---------------- budget ----------------
    title("💰 Budget overview")

    ratio = min(estimated_cost / r_budget, 1.0) if r_budget > 0 else 0.0

    st.progress(
        ratio,
        text=f"₹{estimated_cost:,.0f} estimated / ₹{r_budget:,.0f} maximum budget",
    )

    if estimated_cost <= r_budget:
        st.success(f"✓ The estimated trip cost of ₹{estimated_cost:,.0f} is within your maximum budget of ₹{r_budget:,.0f}.")
    else:
        st.warning(
            f"⚠ The estimated trip cost of ₹{estimated_cost:,.0f} is above your maximum budget of "
            f"₹{r_budget:,.0f}. "
            + ("The agent attempted a lower-cost replan. " if replan_count else "")
            + f"A more realistic budget for this trip is about "
            f"₹{int(math.ceil(estimated_cost / 1000.0) * 1000):,}."
        )

    subtitle(
        "The budget is a maximum constraint — the agent estimates the realistic trip cost "
        "instead of automatically spending the full budget."
    )

    c1, c2, c3 = st.columns(3)

    def money(key: str) -> str:
        return f"₹{float(breakdown.get(key, 0)):,.0f}"

    with c1:
        st.metric("🏨 Accommodation", money("accommodation"))
        st.metric("🍜 Food", money("food"))
    with c2:
        st.metric("🚆 Transport to destination", money("transport_to_destination"))
        st.metric("🚌 Local transport", money("local_transport"))
    with c3:
        st.metric("🎟️ Activities", money("activities"))
        st.metric("🧾 Miscellaneous", money("miscellaneous"))

    # ---------------- agent trace ----------------
    title("🧠 AI planning journey")
    subtitle("A simplified view of the actions performed by the agent.")

    steps: list[tuple[str, str]] = []

    for item in result.get("trace", []):
        action = str(item.get("action", "")).lower()
        obs = item.get("observation", {})

        if action == "goal_received":
            steps.append(("ok", "✓ Understanding your travel requirements"))
        elif action == "destination_database":
            steps.append(("ok", "✓ Checking curated destination information"))
        elif action == "tavily_search":
            found = obs.get("results", 0) if isinstance(obs, dict) else 0
            if found:
                steps.append(("ok", f"✓ Searching destination information on the web ({found} sources)"))
            else:
                steps.append(("warn", "⚠ Web search returned no results"))
        elif action == "calculator":
            steps.append(("ok", "✓ Calculating the estimated trip cost"))
        elif action == "constraint_check":
            if isinstance(obs, dict) and not obs.get("budget", True):
                steps.append(("warn", "⚠ Initial plan exceeded the requested budget"))
            else:
                steps.append(("ok", "✓ Checking trip constraints"))
        elif action == "replan":
            steps.append(("warn", "↻ Replanning the journey to satisfy constraints"))
        elif action == "calculator_after_replan":
            steps.append(("ok", "✓ Recalculating the cost of the revised plan"))
        elif action == "constraint_check_after_replan":
            if isinstance(obs, dict) and not obs.get("budget", True):
                steps.append(("warn", "⚠ Final plan is still above the requested budget"))
            else:
                steps.append(("ok", "✓ Final constraint check passed"))
        elif action == "itinerary_generated":
            steps.append(("ok", "✓ Generating the final itinerary"))
        elif action == "completed":
            steps.append(("ok", "✓ Final journey ready"))

    for kind, message in steps:
        (st.warning if kind == "warn" else st.success)(message)

    # ---------------- itinerary ----------------
    title("🗺️ Your itinerary")

    final_answer = result.get("final_answer", "")

    if final_answer:
        st.markdown(final_answer)
    else:
        st.info("The agent completed the planning process, but no formatted itinerary was returned.")

    itinerary = result.get("itinerary", [])

    if itinerary:
        title("📍 Places included")

        for index, place in enumerate(itinerary, start=1):
            st.info(
                f"**{index}. 📍 {place.get('name', 'Recommended place')}** "
                f"(Day {place.get('day', '?')})\n\n"
                f"{place.get('description', '')}"
            )

    # ---------------- validation ----------------
    title("✅ Plan validation")

    budget_ok = bool(constraints.get("budget", estimated_cost <= r_budget))
    days_covered = {int(p.get("day", 0)) for p in itinerary}
    days_ok = all(d in days_covered for d in range(1, r_days + 1))
    overall_ok = budget_ok and days_ok

    v1, v2, v3 = st.columns(3)

    with v1:
        if budget_ok:
            st.success("✓ Budget satisfied")
        else:
            st.warning("⚠ Budget requires attention")

    with v2:
        if days_ok:
            st.success(f"✓ All {r_days} days planned")
        else:
            st.warning("⚠ Some days have no activities")

    with v3:
        if overall_ok:
            st.success("✓ Plan ready")
        else:
            st.warning("⚠ Plan requires attention")

    title("🤖 Why this is an agent")
    st.info(
        "The system combines an LLM with external tools and short-term state. It searches for "
        "information, calculates costs, checks constraints and can replan instead of producing only "
        "a single static response."
    )


st.markdown(
    '<div class="footer-text">TravelMind AI • Agentic AI Travel Planning System<br>'
    'LLM reasoning • Tool use • Constraint checking • Adaptive replanning</div>',
    unsafe_allow_html=True,
)

