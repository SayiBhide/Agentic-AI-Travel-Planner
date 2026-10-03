from agent.constraints import check_constraints


def test_budget_within_limit():
    result = check_constraints(
        days=2,
        budget=5000,
        total_cost=2800,
        itinerary=[
            {"day": 1, "place": "Place A"},
            {"day": 2, "place": "Place B"},
        ],
    )

    assert result["budget"] is True
    assert result["days"] is True
    assert result["overall"] is True


def test_budget_exceeded():
    result = check_constraints(
        days=2,
        budget=3000,
        total_cost=5400,
        itinerary=[
            {"day": 1, "place": "Place A"},
            {"day": 2, "place": "Place B"},
        ],
    )

    assert result["budget"] is False
    assert result["overall"] is False


def test_invalid_itinerary_day():
    result = check_constraints(
        days=2,
        budget=5000,
        total_cost=2800,
        itinerary=[
            {"day": 1, "place": "Place A"},
            {"day": 3, "place": "Place B"},
        ],
    )

    assert result["days"] is False
    assert result["overall"] is False
    