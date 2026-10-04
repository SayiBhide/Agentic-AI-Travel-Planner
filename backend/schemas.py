from pydantic import BaseModel, Field


class TravelRequest(BaseModel):

    destination: str

    days: int = Field(gt=0)

    travelers: int = Field(gt=0)

    budget: float = Field(gt=0)

    interests: list[str] = Field(
        default_factory=list
    )

    start_location: str = ""


class TravelResponse(BaseModel):

    status: str

    itinerary: list[dict]

    estimated_cost: float

    cost_breakdown: dict[str, float] = Field(
        default_factory=dict
    )

    constraint_results: dict

    replan_count: int

    final_answer: str

    trace: list[dict]
    