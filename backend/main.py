from fastapi import FastAPI

from backend.schemas import TravelRequest, TravelResponse
from agent.agent import run_travel_agent


app = FastAPI(
    title="Agentic AI Travel Planner",
    description="Backend API for an LLM-based travel planning agent",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "message": "Agentic AI Travel Planner backend is running"
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy"
    }


@app.post("/api/trips/plan", response_model=TravelResponse)
def plan_trip(request: TravelRequest):

    result = run_travel_agent(
        destination=request.destination,
        days=request.days,
        travelers=request.travelers,
        budget=request.budget,
        interests=request.interests,
        start_location=request.start_location
    )

    return result