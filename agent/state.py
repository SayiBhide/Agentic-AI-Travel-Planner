from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    # User's travel requirements
    destination: str = ""
    days: int = 1
    travelers: int = 1
    budget: float = 0.0
    interests: list[str] = field(default_factory=list)
    start_location: str = ""

    # Agent's working information
    plan: list[str] = field(default_factory=list)
    observations: list[dict[str, Any]] = field(default_factory=list)

    # Final result
    itinerary: list[dict[str, Any]] = field(default_factory=list)
    total_cost: float = 0.0

    # Constraint results
    constraint_results: dict[str, bool] = field(default_factory=dict)

    # Agent status
    status: str = "initialized"
    iteration: int = 0
    replan_count: int = 0