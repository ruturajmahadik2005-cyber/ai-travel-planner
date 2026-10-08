# AI Travel Planner — Multi-Agent LangGraph + FastAPI

A multi-agent AI Travel Planner built using Python, LangGraph, FastAPI, Google Gemini, and Serper.

The application researches a destination, generates a personalized day-by-day itinerary, pauses for human review, and supports approval, rejection with feedback, or specific modifications before producing the final itinerary.

## Architecture

```text
User
  |
  v
POST /plan
  |
  v
LangGraph Orchestrator
  |
  v
Research Agent
  |
  +--> Serper Real-Time Web Search
  |
  +--> Travel Season Advisor
  |
  v
Itinerary Planner Agent
  |
  +--> Budget Allocator
  |
  +--> Packing Assistant
  |
  v
Human-in-the-Loop Review
  |
  +--> Approve --------> Finalize --------> END
  |
  +--> Reject
  |       |
  |       v
  |    Revision
  |       |
  |       v
  |    Planner
  |       |
  |       +-----------> Human Review
  |
  +--> Modify
          |
          v
       Revision
          |
          v
       Planner
          |
          +-----------> Human Review
```

LangGraph `StateGraph` acts as the workflow orchestrator.

Each travel plan receives a unique `plan_id`, which is also used as the LangGraph `thread_id`.

SQLite-backed LangGraph checkpointing preserves workflow state across Human-in-the-Loop pauses and application restarts.

## Agents

### 1. Research Agent

The Research Agent gathers information required for itinerary planning.

Tools:

- **Serper Web Search** — real-time destination research.
- **Travel Season Advisor** — date-aware seasonal and weather-planning guidance.

The agent uses Gemini to transform the gathered evidence into structured research containing attractions, local tips, safety information, seasonal guidance, and useful sources.

### 2. Itinerary Planner Agent

The Planner Agent creates the personalized itinerary using:

- User travel request
- Research Agent output
- Budget Allocator
- Packing Assistant
- Previous itinerary draft
- Human feedback/modifications

The itinerary includes a summary, day-by-day activities, budget information, packing recommendations, and assumptions.

## Human-in-the-Loop

LangGraph `interrupt()` pauses the workflow after an itinerary draft is generated.

The reviewer can perform three actions:

- `approve` — finalize the current itinerary.
- `reject` — provide feedback and route the workflow back to the Planner Agent.
- `modify` — request specific changes and route the workflow back to the Planner Agent.

After rejection or modification, the revision counter is incremented and a new draft is generated before the workflow pauses again for review.

## Web Interface

The project includes a responsive web interface served directly by FastAPI.

The interface allows users to:

- Enter destination and travel dates
- Set minimum and maximum budget
- Select currency and number of travelers
- Choose travel interests
- Generate an itinerary
- Review the generated itinerary
- Approve the plan
- Request a revision with feedback
- Modify a specific part of the itinerary

The interface communicates with the same FastAPI endpoints used by external API clients.

## API Endpoints

### Create Plan

`POST /plan`

Creates a new travel-planning workflow and returns the generated `plan_id`, current status, and draft.

### Get Plan

`GET /plan/{plan_id}`

Returns the current workflow status and itinerary draft.

### Review Plan

`POST /plan/{plan_id}/review`

Supported actions:

- `approve`
- `reject`
- `modify`

### Get Final Plan

`GET /plan/{plan_id}/final`

Returns the final itinerary only after human approval.

Calling this endpoint before approval returns HTTP `409`.

### Health Check

`GET /health`

Returns API health status.

## Technology Stack

- Python
- FastAPI
- LangGraph
- Google Gemini
- LangChain Google GenAI
- Serper API
- SQLite
- LangGraph SQLite Checkpointer
- Pydantic
- Requests
- Uvicorn
- python-dotenv
- HTML
- CSS
- JavaScript

## Setup

Python 3.11+ is recommended.

### 1. Create Virtual Environment

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy:

```text
.env.example
```

to:

```text
.env
```

Configure:

```env
GOOGLE_API_KEY=your_google_gemini_api_key
GEMINI_MODEL=gemini-3.8-flash
SERPER_API_KEY=your_serper_api_key
```

Never commit `.env` or real API keys to Git.

### 4. Run Application

```bash
uvicorn app.main:app --reload
```

Web interface:

```text
http://127.0.0.1:8000
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

## Example API Flow

### 1. Create Travel Plan

Request:

```bash
curl -X POST "http://127.0.0.1:8000/plan" \
-H "Content-Type: application/json" \
-d '{
  "destination": "Goa, India",
  "start_date": "2026-11-10",
  "end_date": "2026-11-13",
  "budget_min": 20000,
  "budget_max": 30000,
  "interests": [
    "beaches",
    "local food",
    "culture",
    "nature"
  ],
  "travelers": 2,
  "currency": "INR"
}'
```

Example response:

```json
{
  "plan_id": "generated-plan-id",
  "status": "awaiting_review",
  "workflow_paused": true,
  "draft": {
    "summary": "Personalized Goa itinerary",
    "days": []
  },
  "revision_count": 0
}
```

### 2. Check Current Plan

```bash
curl "http://127.0.0.1:8000/plan/PLAN_ID"
```

### 3. Reject and Request Revision

```bash
curl -X POST "http://127.0.0.1:8000/plan/PLAN_ID/review" \
-H "Content-Type: application/json" \
-d '{
  "action": "reject",
  "feedback": "Reduce expensive activities and add more local food experiences."
}'
```

The workflow routes back to the Planner Agent and generates another draft.

### 4. Request Specific Modification

```bash
curl -X POST "http://127.0.0.1:8000/plan/PLAN_ID/review" \
-H "Content-Type: application/json" \
-d '{
  "action": "modify",
  "modifications": {
    "day_2_evening": "Replace the evening activity with a relaxed beach sunset and local food experience."
  }
}'
```

The Planner Agent receives the previous draft and requested modifications, creates an updated draft, and pauses again for review.

### 5. Approve Plan

```bash
curl -X POST "http://127.0.0.1:8000/plan/PLAN_ID/review" \
-H "Content-Type: application/json" \
-d '{
  "action": "approve"
}'
```

### 6. Retrieve Final Plan

```bash
curl "http://127.0.0.1:8000/plan/PLAN_ID/final"
```

The final endpoint is available only after approval.

## Persistence

The application uses:

```text
langgraph-checkpoint-sqlite
```

LangGraph checkpoints are stored locally in:

```text
travel_planner.db
```

This provides durable workflow state across API requests, Human-in-the-Loop pauses, and local application restarts.

The SQLite database is excluded from Git using `.gitignore`.

For a production deployment, PostgreSQL or another production-grade persistent checkpoint store would be preferable.

## LLM Failure Handling

The Gemini integration includes basic failure handling.

Temporary service errors such as HTTP `503` are retried with a short delay.

Quota errors such as HTTP `429` are not repeatedly retried.

Gemini requests use a timeout to prevent a network problem from leaving the workflow waiting indefinitely.

If Gemini is unavailable, the application can return a deterministic fallback research result or itinerary so that the API and LangGraph workflow remain functional.

The fallback is intended for graceful degradation and development/testing rather than replacing normal LLM-generated output.

## Design Decisions and Tradeoffs

The agents are implemented as explicit LangGraph nodes instead of using an opaque autonomous-agent loop. This makes workflow routing, state transitions, revision behavior, and Human-in-the-Loop handling easier to inspect and test.

Serper provides the required real-time web research capability.

The complementary Travel Season Advisor intentionally avoids pretending to provide exact long-range forecasts. It provides date-aware planning guidance while current destination information can be gathered through real-time web search.

The Budget Allocator and Packing Assistant are deterministic tools. This makes their output predictable while Gemini focuses on reasoning over research and producing the itinerary.

SQLite was selected for local durable checkpoint persistence because it is lightweight and requires no external database service.

Pydantic validates incoming API requests, including travel dates, budget ranges, traveler counts, and review requirements.

A lightweight web interface is included for easier demonstration of the complete workflow without adding a separate frontend framework.

## Assumptions

- Search results are research evidence and are not treated as guaranteed truth.
- Budget allocations are planning estimates, not live booking prices.
- The system does not book hotels, flights, restaurants, activities, or tickets.
- Exact weather should be verified closer to the travel date.
- External API availability and free-tier limits may affect LLM or search responses.
- A valid Gemini API key and Serper API key are required for the complete AI-powered experience.

## Production Improvements

With more development time, the project could include:

- PostgreSQL-backed LangGraph persistence
- Authentication and per-user authorization
- Rate limiting
- Structured logging and monitoring
- Automated unit and integration tests
- Source-quality scoring
- More detailed source citations
- Live weather API integration
- Hotel and flight integrations
- Travel-time and route optimization
- Redis caching
- Background task processing
- Docker and Docker Compose
- CI/CD pipeline
- LLM evaluation datasets
- Prompt/version management
- Token and API cost monitoring

## Project Structure

```text
ai_travel_planner/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── tools.py
│   ├── workflow.py
│   ├── static/
│   │   ├── app.js
│   │   └── style.css
│   └── templates/
│       └── index.html
├── .env.example
├── .env                 # Local only - gitignored
├── travel_planner.db    # Local runtime DB - gitignored
├── .gitignore
├── requirements.txt
└── README.md
```

> `.env` and `travel_planner.db` are local runtime files and are excluded from Git using `.gitignore`.

The virtual environment, Python cache files, and other generated local files are also excluded from Git.

## Security

Secrets are loaded from environment variables using `python-dotenv`.

Real API keys must never be placed in:

- Source code
- README
- `.env.example`
- Git commits

Only placeholder values should be included in `.env.example`.

## Summary

This project demonstrates:

- Multi-agent workflow orchestration with LangGraph
- Real-time research using Serper
- LLM-powered research synthesis and itinerary generation
- Explicit Research and Planner agents
- Multiple agent tools
- Human-in-the-Loop review
- Approve, reject, and modify workflows
- Durable SQLite state persistence
- FastAPI REST endpoints
- Responsive web interface
- Input validation
- Graceful external API failure handling

## Author

**Ruturaj Mahadik**

