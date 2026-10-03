# TravelMind AI – Agentic AI Travel Planning System

## 1. Project Overview

TravelMind AI is an LLM-based Agentic AI system designed to generate personalized travel itineraries based on a user's destination, trip duration, number of travelers, budget, interests, and starting location.

Unlike a simple chatbot that directly generates a response, the system follows an agentic workflow in which the agent interprets the user's goal, plans intermediate actions, uses external and local tools, observes the results, checks constraints, and replans when the generated plan does not satisfy the user's requirements.

The system is implemented using Python, Streamlit, FastAPI, OpenRouter, Tavily Web Search, a calculator tool, and a small local destination knowledge base.

---

## 2. Objectives

The main objectives of the project are:

* To understand the working of modern LLM-based Agentic AI systems.
* To implement an agent capable of multi-step planning.
* To integrate external and local tools into an AI workflow.
* To demonstrate short-term contextual memory using an AgentState.
* To perform deterministic constraint checking.
* To demonstrate automatic replanning when constraints are violated.
* To maintain observable execution traces of the agent's actions.
* To provide an interactive travel planning interface using Streamlit.

---

## 3. Key Features

### Personalized Travel Planning

The user can provide:

* Destination
* Number of days
* Number of travelers
* Budget
* Travel interests
* Starting location

### LLM-Based Reasoning

The system uses an LLM through OpenRouter to transform the user's requirements and collected information into a structured travel itinerary.

### Web Search Tool

Tavily Web Search is used to retrieve destination-specific information.

The planner is not restricted to the destinations stored in the local database. For destinations outside the local demonstration database, the web-search tool provides relevant destination information.

### Local Destination Knowledge Base

A small JSON-based knowledge source contains selected demonstration places and their information such as:

* Place name
* City
* Category
* Description
* Estimated duration
* Entry fee
* Opening information
* Interest tags

### Calculator Tool

A deterministic calculator tool is used to estimate the trip cost based on the number of days and travelers.

### Constraint Checking

The system checks important user constraints including:

* Budget
* Number of days
* Itinerary day validity

### Automatic Replanning

If the initial estimated plan exceeds the user's budget, the agent performs a replanning step and generates a revised plan.

### Observable Agent Trace

The system records important stages of execution, including:

* Goal received
* Destination knowledge lookup
* Web search
* Cost calculation
* Constraint checking
* Replanning
* Itinerary generation
* Completion

---

## 4. System Architecture

```text
                 User
                   |
                   v
          +------------------+
          |    Streamlit     |
          |   User Interface |
          +------------------+
                   |
                   v
          +------------------+
          | Agent Controller |
          +------------------+
                   |
        +----------+----------+
        |          |          |
        v          v          v
   Tavily Web   Calculator   Local
     Search       Tool       JSON DB
        |          |          |
        +----------+----------+
                   |
                   v
          +------------------+
          | Constraint       |
          | Checker          |
          +------------------+
                   |
             Constraint
                Failed?
              /         \
            Yes          No
             |            |
             v            |
        Replanning        |
             |            |
             +------->----+
                   |
                   v
          +------------------+
          | Final Itinerary  |
          +------------------+
                   |
                   v
             User Output
```

FastAPI is also included as a backend API component for structured request/response handling and API-based execution.

---

## 5. Agent Workflow

The agent follows a multi-step workflow:

```text
User Goal
   ↓
Understand Requirements
   ↓
Create Initial Plan
   ↓
Search Destination Information
   ↓
Observe Tool Results
   ↓
Calculate Estimated Cost
   ↓
Check Constraints
   ↓
Constraint Failed?
   ↓
Replan if Required
   ↓
Generate Final Itinerary
   ↓
Return Result + Planning Trace
```

This demonstrates the agentic cycle:

```text
Reason → Act → Observe → Update → Replan → Act
```

---

## 6. Tools Integrated

| Tool               | Purpose                                             |
| ------------------ | --------------------------------------------------- |
| OpenRouter LLM     | Natural-language reasoning and itinerary generation |
| Tavily Web Search  | Destination-specific web information                |
| Calculator         | Deterministic cost calculation                      |
| Destination JSON   | Local structured destination knowledge              |
| Constraint Checker | Validates budget and itinerary requirements         |
| AgentState         | Maintains short-term planning context               |

---

## 7. Technology Stack

### Programming Language

Python

### Frontend

Streamlit

### Backend API

FastAPI

### LLM Provider

OpenRouter

### Web Search

Tavily

### Data Storage

JSON-based local destination knowledge base

### Validation

Pydantic

### Version Control

Git and GitHub

### Deployment

Streamlit Community Cloud

---

## 8. Project Structure

```text
Agentic_AI_Travel_Planner/
│
├── agent/
│   ├── agent.py
│   ├── constraints.py
│   └── state.py
│
├── backend/
│   ├── main.py
│   └── schemas.py
│
├── data/
│   └── destinations.json
│
├── frontend/
│   └── streamlit_app.py
│
├── tests/
│   └── test_constraints.py
│
├── tools/
│   ├── calculator.py
│   ├── destination_db.py
│   └── web_search.py
│
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

---

## 9. Example Demonstration

### Scenario 1 – Budget Constraint and Replanning

Input:

* Destination: Mathura & Vrindavan
* Duration: 2 days
* Travelers: 4
* Budget: ₹3,000
* Interests: Temples & Culture, Food
* Starting location: Mathura Railway Station

The initial cost estimate exceeds the specified budget.

The constraint checker therefore identifies a budget violation and triggers the replanning stage.

The revised plan produces an estimated cost of ₹2,800 and satisfies the requested budget.

This demonstrates that the system does not simply generate a response once. It evaluates the generated planning conditions and performs another planning step when a constraint is violated.

---

### Scenario 2 – General Destination

Input:

* Destination: Goa
* Duration: 2 days
* Travelers: 4
* Budget: ₹10,000
* Interests: Food, Beaches, Sightseeing
* Starting location: Goa Airport

The estimated cost remains within the specified budget, so no replanning is required.

The system generates a two-day itinerary based on the destination information retrieved through the available tools.

The application is destination-agnostic. Mathura and Vrindavan are demonstration destinations, not a limitation of the system.

---

## 10. Important Implementation Note

The cost values produced by the calculator are planning estimates used for constraint checking. They are not live hotel, transport, ticket, or booking quotations.

Similarly, web-search results are used as information sources for planning and should be verified by users before making real travel bookings.

---

## 11. Running the Project Locally

### Step 1 – Create and activate the virtual environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 2 – Install dependencies

```powershell
pip install -r requirements.txt
```

### Step 3 – Configure API keys

Create:

```text
.streamlit/secrets.toml
```

and add the required OpenRouter and Tavily API keys.

### Step 4 – Start the Streamlit application

Run from the project root:

```powershell
streamlit run frontend/streamlit_app.py
```

The application will open in the browser.

---

## 12. FastAPI Backend

The FastAPI backend can be run separately using:

```powershell
uvicorn backend.main:app --reload
```

The API provides:

```text
GET  /
GET  /api/health
POST /api/trips/plan
```

The backend provides a structured API interface for the agent and can also be used independently for testing.

---

## 13. Testing

The project contains deterministic tests for the constraint-checking component.

Tests can be executed using:

```powershell
pytest
```

---

## 14. Deployment

The Streamlit interface can be deployed using Streamlit Community Cloud.

The GitHub repository acts as the source repository for the deployed application.

After deployment, changes committed and pushed to the connected GitHub repository can automatically be reflected in the deployed Streamlit application.

API keys are configured through Streamlit's deployment secrets rather than being stored in the GitHub repository.

---

## 15. Academic Relevance

This project demonstrates the transition from traditional rule-based AI systems toward modern LLM-based Agentic AI.

A classical system generally follows predefined rules and fixed decision paths. The implemented system instead combines an LLM with external tools, short-term state, constraint checking, and replanning.

The project therefore demonstrates:

* LLM-based reasoning
* Tool usage
* Multi-step planning
* Contextual state
* Constraint validation
* Replanning
* Observable agent execution
* Human-readable final generation

---

## 16. Limitations

The current implementation focuses on demonstrating agentic planning rather than providing a production-grade travel booking platform.

The system does not directly perform:

* Hotel booking
* Flight booking
* Payment
* Ticket reservation
* Real-time booking confirmation

The estimated cost is intended for planning and constraint checking rather than guaranteed pricing.

---

## 17. Future Scope

Possible future extensions include:

* Real-time hotel and flight APIs
* Route optimization
* Calendar integration
* Persistent user preferences
* More comprehensive destination databases
* Voice-based travel assistance
* Real-time weather integration
* Multi-agent travel planning
* Booking and reservation integration

---

## 18. Team

**Project:** Agentic AI Travel Planning System

**Subject:** Artificial Intelligence

**Academic Year:** 2026–27

**Department:** Computer Science and Business Systems

---

## 19. License

This project is developed for academic and educational purposes.
