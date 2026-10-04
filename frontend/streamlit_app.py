import sys
from pathlib import Path

import streamlit as st


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from agent.agent import run_travel_agent


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="TravelMind AI",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .stApp {
        background-color: #FFF9F3;
    }

    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }

    header {
        background: transparent !important;
    }

    /* Hero */

    .hero-title-text {
        color: #12355B;
        font-size: 46px;
        font-weight: 850;
        line-height: 1.05;
        margin: 4px 0 8px 0;
    }

    .hero-subtitle-text {
        color: #536878;
        font-size: 17px;
        line-height: 1.65;
        max-width: 850px;
        margin-bottom: 8px;
    }

    .hero-note-text {
        color: #176B87;
        font-size: 14px;
        font-weight: 650;
        margin-bottom: 20px;
    }

    .hero-badge-text {
        color: #176B87;
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0.7px;
        margin-bottom: 2px;
    }

    /* Section headings */

    .section-title-text {
        color: #12355B;
        font-size: 27px;
        font-weight: 800;
        margin-top: 24px;
        margin-bottom: 3px;
    }

    .section-subtitle-text {
        color: #718096;
        font-size: 14px;
        margin-bottom: 15px;
    }

    /* Buttons */

    .stButton > button {
        border-radius: 13px;
        font-weight: 750;
        min-height: 46px;
    }

    .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #FF7A59, #FF9F68);
        border: none;
    }

    /* Inputs */

    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div {
        border-radius: 11px;
    }

    /* Metrics */

    div[data-testid="stMetric"] {
        background: white;
        border: 1px solid #F0E4D8;
        border-radius: 16px;
        padding: 15px 17px;
        box-shadow: 0 5px 16px rgba(40, 70, 90, 0.05);
    }

    div[data-testid="stMetricLabel"] {
        color: #718096;
    }

    div[data-testid="stMetricValue"] {
        color: #12355B;
    }

    /* Expanders */

    div[data-testid="stExpander"] {
        border: 1px solid #E9DED3;
        border-radius: 14px;
        background: white;
    }

    /* Footer */

    .footer-text {
        text-align: center;
        color: #8A98A5;
        font-size: 12px;
        margin-top: 42px;
        padding-top: 20px;
        border-top: 1px solid #EDE2D8;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATE
# ============================================================

if "result" not in st.session_state:
    st.session_state.result = None


# ============================================================
# HERO
# ============================================================

st.markdown(
    '<div class="hero-badge-text">'
    '✨ AI-POWERED • TOOL-USING • ADAPTIVE'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="hero-title-text">🌴 TravelMind AI</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="hero-subtitle-text">'
    'Your intelligent travel planning agent that searches destination '
    'information, reasons over your requirements, calculates estimated '
    'costs and adapts the journey when constraints are not satisfied.'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="hero-note-text">'
    '🌍 Plan trips for any destination'
    '</div>',
    unsafe_allow_html=True,
)

st.divider()


# ============================================================
# INPUT SECTION
# ============================================================

st.markdown(
    '<div class="section-title-text">Plan your journey</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="section-subtitle-text">'
    'Tell the agent what kind of trip you want.'
    '</div>',
    unsafe_allow_html=True,
)

input_left, input_right = st.columns(2)


with input_left:

    destination = st.text_input(
        "📍 Destination",
        value="Mathura & Vrindavan",
        placeholder="Goa, Manali, Jaipur, Paris...",
    )

    start_location = st.text_input(
        "🚉 Starting location",
        value="Mathura Railway Station",
        placeholder="Airport, railway station, hotel or city",
    )

    days = st.number_input(
    "🗓️ Number of days",
    min_value=1,
    max_value=365,
    value=2,
    step=1
    )


with input_right:

    travelers = st.number_input(
    "👥 Number of travelers",
    min_value=1,
    max_value=100,
    value=4,
    step=1
    )

    budget = st.number_input(
    "💰 Total trip budget (₹)",
    min_value=100,
    max_value=10000000,
    value=5000,
    step=500
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

    selected_interest_labels = st.multiselect(
        "❤️ Travel interests",
        options=list(interest_options.keys()),
        default=[
            "🛕 Temples & Culture",
            "🍜 Food",
        ],
    )

    interests = [
        interest_options[label]
        for label in selected_interest_labels
    ]


# ============================================================
# ACTION BUTTON
# ============================================================

button_col1, button_col2, button_col3 = st.columns([1, 2, 1])

with button_col2:

    plan_trip = st.button(
        "✈️ Plan My Journey",
        use_container_width=True,
        type="primary",
    )


# ============================================================
# INTRODUCTION BEFORE FIRST PLAN
# ============================================================

if st.session_state.result is None and not plan_trip:

    st.info(
        "🤖 **How TravelMind AI works**\n\n"
        "TravelMind AI does more than generate a fixed itinerary. "
        "The agent understands the trip requirements, gathers information "
        "using external tools, estimates costs, checks constraints and "
        "can revise its plan when the initial plan does not satisfy them."
    )

    st.success(
        "💡 **Agentic example:** If the initial plan exceeds the requested "
        "budget, the agent can trigger a replanning step and generate a "
        "revised plan."
    )


# ============================================================
# PLAN REQUEST
# ============================================================

if plan_trip:

    if not destination.strip():

        st.error("Please enter a destination.")

    elif not selected_interest_labels:

        st.error("Please select at least one travel interest.")

    else:

        with st.spinner(
            "🤖 Your travel agent is searching, calculating and planning..."
        ):

            try:

                result = run_travel_agent(
                    destination=destination.strip(),
                    days=int(days),
                    travelers=int(travelers),
                    budget=float(budget),
                    interests=interests,
                    start_location=start_location.strip(),
                )

                st.session_state.result = result

                st.rerun()

            except Exception as error:

                st.error(
                    "The travel agent could not complete the request."
                )

                with st.expander("Technical details"):

                    st.code(str(error))


# ============================================================
# DISPLAY RESULTS
# ============================================================

if st.session_state.result is not None:

    result = st.session_state.result

    # --------------------------------------------------------
    # RESULT VALUES
    # Keep these values available to every result section.
    # --------------------------------------------------------

    estimated_cost = float(
        result.get("estimated_cost", 0)
    )

    replan_count = int(
        result.get("replan_count", 0)
    )

    # --------------------------------------------------------
    # NEW TRIP BUTTON
    # --------------------------------------------------------

    top_left, top_right = st.columns([5, 1])

    with top_right:

        if st.button(
            "↻ New Trip",
            use_container_width=True,
        ):

            st.session_state.result = None
            st.rerun()


    # --------------------------------------------------------
    # SUCCESS MESSAGE
    # --------------------------------------------------------

    st.success(
        f"✓ Journey planned successfully for **{destination}**. "
        "The agent completed its planning and validation process."
    )


    # --------------------------------------------------------
    # RESULT SUMMARY
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title-text">'
        'Your AI-planned journey'
        '</div>',
        unsafe_allow_html=True,
    )

    metric1, metric2, metric3, metric4 = st.columns(4)

    with metric1:

        st.metric(
            "📍 Destination",
            destination,
        )

    with metric2:

        st.metric(
            "🗓️ Duration",
            f"{int(days)} day{'s' if int(days) != 1 else ''}",
        )

    with metric3:

        st.metric(
            "💰 Estimated cost",
            f"₹{estimated_cost:,.0f}",
        )

    with metric4:

        st.metric(
            "🔄 AI replans",
            replan_count,
        )

    # --------------------------------------------------------
    # BUDGET
    # --------------------------------------------------------

    st.markdown(
       '<div class="section-title-text">'
       '💰 Budget overview'
       '</div>',
       unsafe_allow_html=True,
    )

    # Get the estimated cost directly from the agent result.
    # This keeps the budget section independent of earlier variables.
    estimated_cost = float(
    result.get("estimated_cost", 0)
    )

    budget_ratio = 0.0

    if float(budget) > 0:

      budget_ratio = min(
        estimated_cost / float(budget),
        1.0,
      )

    st.progress(
      budget_ratio,
      text=(
         f"₹{estimated_cost:,.0f} estimated / "
         f"₹{float(budget):,.0f} maximum budget"
      ),
    )

    if estimated_cost <= float(budget):

     st.success(
        f"✓ The estimated trip cost of "
        f"₹{estimated_cost:,.0f} is within your "
        f"maximum budget of ₹{float(budget):,.0f}."
     )

    else:

     st.warning(
        f"⚠ The estimated trip cost of "
        f"₹{estimated_cost:,.0f} is above your "
        f"maximum budget of ₹{float(budget):,.0f}. "
        f"The agent attempted a lower-cost replan."
     )

   # --------------------------------------------------------
   # COST BREAKDOWN
   # --------------------------------------------------------

    cost_breakdown = result.get(
    "cost_breakdown",
    {}
    )

    if cost_breakdown:

     st.markdown(
        '<div class="section-subtitle-text">'
        'The budget is a maximum constraint — the agent estimates '
        'the realistic trip cost instead of automatically spending '
        'the full budget.'
        '</div>',
        unsafe_allow_html=True,
    )

    cost1, cost2, cost3 = st.columns(3)

    with cost1:

        st.metric(
            "🏨 Accommodation",
            f"₹{float(cost_breakdown.get('accommodation', 0)):,.0f}",
        )

        st.metric(
            "🍜 Food",
            f"₹{float(cost_breakdown.get('food', 0)):,.0f}",
        )

    with cost2:

        st.metric(
            "🚆 Transport",
            f"₹{float(cost_breakdown.get('transport_to_destination', 0)):,.0f}",
        )

        st.metric(
            "🚌 Local transport",
            f"₹{float(cost_breakdown.get('local_transport', 0)):,.0f}",
        )

    with cost3:

        st.metric(
            "🎟️ Activities",
            f"₹{float(cost_breakdown.get('activities', 0)):,.0f}",
        )

        st.metric(
            "🧾 Miscellaneous",
            f"₹{float(cost_breakdown.get('miscellaneous', 0)):,.0f}",
        )

    # --------------------------------------------------------
    # AGENTIC PLANNING PROCESS
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title-text">'
        '🧠 AI planning journey'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="section-subtitle-text">'
        'A simplified view of the actions performed by the agent.'
        '</div>',
        unsafe_allow_html=True,
    )

    trace = result.get("trace", [])

    process_items = []

    for item in trace:

        action = str(
            item.get("action", "")
        ).lower()

        observation = item.get(
            "observation",
            {},
        )

        if action == "goal_received":

            process_items.append(
                ("normal", "✓ Understanding your travel requirements")
            )

        elif action == "destination_database":

            process_items.append(
                ("normal", "✓ Checking curated destination information")
            )

        elif action in [
            "web_search",
            "tavily_search",
        ]:

            process_items.append(
                (
                    "normal",
                    "✓ Searching destination information on the web",
                )
            )

        elif action == "calculator":

            process_items.append(
                (
                    "normal",
                    "✓ Calculating the estimated trip cost",
                )
            )

        elif action in [
            "constraint_check",
            "constraint_check_initial",
            "constraint_check_after_replan",
        ]:

            budget_ok = True

            if isinstance(observation, dict):

                if "budget" in observation:

                    budget_ok = bool(
                        observation.get("budget")
                    )

            if budget_ok:

                process_items.append(
                    (
                        "normal",
                        "✓ Checking trip constraints",
                    )
                )

            else:

                process_items.append(
                    (
                        "replan",
                        "⚠ Initial plan exceeded the requested budget",
                    )
                )

        elif action == "replan":

            process_items.append(
                (
                    "replan",
                    "↻ Replanning the journey to satisfy constraints",
                )
            )

        elif action == "itinerary_generated":

            process_items.append(
                (
                    "normal",
                    "✓ Generating the final itinerary",
                )
            )

        elif action == "completed":

            process_items.append(
                (
                    "normal",
                    "✓ Final journey ready",
                )
            )


    # Remove consecutive duplicate steps

    cleaned_process = []

    for item in process_items:

        if not cleaned_process or item != cleaned_process[-1]:

            cleaned_process.append(item)


    if cleaned_process:

        for item_type, message in cleaned_process:

            if item_type == "replan":

                st.warning(message)

            else:

                st.success(message)

    else:

        st.info(
            "The agent completed its planning process."
        )


    # --------------------------------------------------------
    # FINAL ITINERARY
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title-text">'
        '🗺️ Your itinerary'
        '</div>',
        unsafe_allow_html=True,
    )

    final_answer = result.get(
        "final_answer",
        "",
    )

    if final_answer:

        st.markdown(final_answer)

    else:

        st.info(
            "The agent completed the planning process, "
            "but no formatted itinerary was returned."
        )


    # --------------------------------------------------------
    # SELECTED PLACES
    # --------------------------------------------------------

    itinerary = result.get(
        "itinerary",
        [],
    )

    if itinerary:

        st.markdown(
            '<div class="section-title-text">'
            '📍 Places included'
            '</div>',
            unsafe_allow_html=True,
        )

        for index, place in enumerate(
            itinerary,
            start=1,
        ):

            place_name = place.get(
                "name",
                place.get(
                    "place",
                    "Recommended place",
                ),
            )

            description = place.get(
                "description",
                "Recommended as part of your travel plan.",
            )

            st.info(
                f"**{index}. 📍 {place_name}**\n\n"
                f"{description}"
            )


    # --------------------------------------------------------
    # PLAN VALIDATION
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title-text">'
        '✅ Plan validation'
        '</div>',
        unsafe_allow_html=True,
    )

    budget_ok = (
        estimated_cost <= float(budget)
    )

    duration_ok = bool(final_answer)

    overall_ok = (
        budget_ok and duration_ok
    )

    validation1, validation2, validation3 = st.columns(3)

    with validation1:

        if budget_ok:

            st.success("✓ Budget satisfied")

        else:

            st.warning("⚠ Budget requires attention")

    with validation2:

        if duration_ok:

            st.success(
                f"✓ {int(days)}-day plan generated"
            )

        else:

            st.warning(
                "⚠ Duration could not be verified"
            )

    with validation3:

        if overall_ok:

            st.success("✓ Plan ready")

        else:

            st.warning(
                "⚠ Plan requires attention"
            )


    # --------------------------------------------------------
    # PROJECT EXPLANATION
    # --------------------------------------------------------

    st.markdown(
        '<div class="section-title-text">'
        '🤖 Why this is an agent'
        '</div>',
        unsafe_allow_html=True,
    )

    st.info(
        "The system combines an LLM with external tools and short-term "
        "state. It searches for information, calculates costs, checks "
        "constraints and can replan instead of producing only a single "
        "static response."
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    '<div class="footer-text">'
    'TravelMind AI • Agentic AI Travel Planning System<br>'
    'LLM reasoning • Tool use • Constraint checking • Adaptive replanning'
    '</div>',
    unsafe_allow_html=True,
)
