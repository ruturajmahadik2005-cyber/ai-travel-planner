import json
import os
import time
import sqlite3
from datetime import date
from typing import TypedDict, Any

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_google_genai import ChatGoogleGenerativeAI

from .tools import (
    web_search,
    weather_tool,
    budget_allocator,
    packing_tool,
)

# Load environment variables from .env
load_dotenv()


class TravelState(TypedDict, total=False):
    plan_id: str
    request: dict[str, Any]
    research: dict[str, Any]
    draft: dict[str, Any]
    review: dict[str, Any]
    final: dict[str, Any]
    status: str
    revision_count: int


def llm_json(system: str, payload: dict) -> dict | None:
    """
    Call Gemini and return a JSON object.

    Retry temporary service errors such as 503.
    Do not retry quota errors such as 429.
    """

    if not os.getenv("GOOGLE_API_KEY"):
        print("Gemini error: GOOGLE_API_KEY is not configured.")
        return None

    for attempt in range(3):
        try:
            llm = ChatGoogleGenerativeAI(
                model=os.getenv(
                    "GEMINI_MODEL",
                    "gemini-3.8-flash",
                ),
                temperature=0.2,
            )

            response = llm.invoke(
                [
                    (
                        "system",
                        system
                        + "\nReturn only valid JSON. "
                        + "Do not use markdown code fences.",
                    ),
                    (
                        "user",
                        json.dumps(payload, default=str),
                    ),
                ]
            )

            content = response.content

            # Handle Gemini responses that may contain
            # multiple structured content parts.
            if isinstance(content, list):
                parts = []

                for part in content:
                    if isinstance(part, dict):
                        parts.append(part.get("text", ""))
                    else:
                        parts.append(str(part))

                content = "".join(parts)

            content = str(content).strip()

            # Remove markdown JSON fences if the model
            # returns them despite the instruction.
            if content.startswith("```"):
                content = content.replace(
                    "```json",
                    "",
                    1,
                )
                content = content.replace(
                    "```",
                    "",
                )
                content = content.strip()

            result = json.loads(content)

            if not isinstance(result, dict):
                raise ValueError(
                    "Gemini did not return a JSON object."
                )

            return result

        except Exception as e:
            error_text = str(e)

            print(
                f"Gemini attempt "
                f"{attempt + 1}/3 failed: "
                f"{error_text}"
            )

            # Do not retry when free-tier quota
            # has been exhausted.
            if (
                "RESOURCE_EXHAUSTED" in error_text
                or "429" in error_text
                or "quota" in error_text.lower()
            ):
                print(
                    "Gemini quota exhausted. "
                    "Skipping retries."
                )
                return None

            # Retry temporary Gemini/server errors.
            if (
                "UNAVAILABLE" in error_text
                or "503" in error_text
                or "high demand" in error_text.lower()
            ):
                if attempt < 2:
                    wait_seconds = 3 * (attempt + 1)

                    print(
                        "Temporary Gemini error. "
                        f"Retrying in "
                        f"{wait_seconds} seconds..."
                    )

                    time.sleep(wait_seconds)
                    continue

            # Authentication, invalid model, JSON parsing,
            # and other errors should not waste requests.
            print(
                "Non-retryable Gemini error."
            )
            return None

    print(
        "Gemini failed after 3 attempts."
    )
    return None


def research_agent(
    state: TravelState,
) -> dict:
    """
    Research Agent

    Uses:
    1. Serper web search
    2. Weather/complementary tool

    Gemini then analyzes the gathered research.
    """

    request = state["request"]

    query = (
        f"{request['destination']} travel "
        f"attractions things to do local tips safety "
        f"weather {request['start_date']} "
        f"{request['end_date']}"
    )

    search_results = web_search(query)

    weather = weather_tool(
        request["destination"],
        request["start_date"],
        request["end_date"],
    )

    research = llm_json(
        """
You are the Research Agent in a multi-agent
AI Travel Planner.

Analyze the supplied real-time web-search
results and weather information.

Return a JSON object with this structure:

{
  "attractions": [],
  "local_tips": [],
  "safety": [],
  "weather": {},
  "seasonal": [],
  "sources": []
}

Requirements:
- Use the supplied research evidence.
- Prefer practical and relevant information.
- Do not invent unsupported real-time facts.
- Preserve useful source URLs.
- Focus on information useful for itinerary planning.
""",
        {
            "travel_request": request,
            "web_search_results": search_results,
            "weather_information": weather,
        },
    )

    # Safe fallback if Gemini is unavailable.
    if research is None:
        research = {
            "attractions": [],
            "local_tips": [],
            "safety": [],
            "weather": weather,
            "seasonal": [],
            "sources": search_results,
        }

    return {
        "research": research,
        "status": "researched",
    }


def planner_agent(
    state: TravelState,
) -> dict:
    """
    Itinerary Planner Agent

    Uses:
    1. Budget allocation tool
    2. Packing recommendation tool

    It also consumes the Research Agent output.
    """

    request = state["request"]

    start = request["start_date"]
    end = request["end_date"]

    if isinstance(start, str):
        start_obj = date.fromisoformat(start)
    else:
        start_obj = start

    if isinstance(end, str):
        end_obj = date.fromisoformat(end)
    else:
        end_obj = end

    days = (
        end_obj - start_obj
    ).days + 1

    days = max(days, 1)

    budget = budget_allocator(
        request["budget_min"],
        request["budget_max"],
        request["travelers"],
        days,
    )

    packing = packing_tool(
        request["interests"],
        days,
    )

    review = state.get(
        "review",
        {},
    )

    draft = llm_json(
        """
You are the Itinerary Planner Agent in a
multi-agent AI Travel Planner.

Using:
- the user's travel request,
- Research Agent findings,
- budget allocation,
- packing recommendations,
- and any human review feedback,

create a practical day-by-day itinerary.

Return a JSON object with this structure:

{
  "summary": "...",
  "days": [
    {
      "day": 1,
      "date": "YYYY-MM-DD",
      "morning": "...",
      "afternoon": "...",
      "evening": "...",
      "notes": "..."
    }
  ],
  "budget": {},
  "packing": [],
  "assumptions": []
}

Important requirements:

- Respect the requested travel dates.
- Respect the requested budget range.
- Consider the number of travelers.
- Consider the user's interests.
- Use the Research Agent findings.
- Keep the itinerary realistic.
- Do not claim hotels, flights, restaurants,
  activities, or tickets have actually been booked.

Human review behavior:

- If rejection feedback is supplied, revise
  the previous itinerary according to the feedback.

- If modifications are supplied, apply the
  requested changes while keeping unaffected
  parts of the itinerary consistent.
""",
        {
            "travel_request": request,
            "research": state.get(
                "research",
                {},
            ),
            "budget_tool_result": budget,
            "packing_tool_result": packing,
            "previous_draft": state.get(
                "draft"
            ),
            "human_review": review,
        },
    )

    # Fallback itinerary if Gemini cannot respond.
    if draft is None:
        draft = {
            "summary": (
                f"{days}-day trip to "
                f"{request['destination']}"
            ),
            "days": [
                {
                    "day": i + 1,
                    "date": str(
                        start_obj.fromordinal(
                            start_obj.toordinal() + i
                        )
                    ),
                    "morning": (
                        "Explore a researched attraction"
                    ),
                    "afternoon": (
                        "Explore a local area or activity"
                    ),
                    "evening": (
                        "Local dining and relaxed activity"
                    ),
                    "notes": (
                        "Fallback itinerary generated "
                        "because the Gemini response "
                        "was unavailable."
                    ),
                }
                for i in range(days)
            ],
            "budget": budget,
            "packing": packing,
            "assumptions": [
                "Gemini API response was unavailable."
            ],
        }

    return {
        "draft": draft,
        "status": "awaiting_review",
    }


def human_review(
    state: TravelState,
) -> dict:
    """
    Human-in-the-loop review point.

    LangGraph pauses execution here until
    the /review API resumes the graph.
    """

    decision = interrupt(
        {
            "message": (
                "Review the generated itinerary."
            ),
            "plan_id": state.get(
                "plan_id"
            ),
            "draft": state.get(
                "draft"
            ),
            "allowed_actions": [
                "approve",
                "reject",
                "modify",
            ],
        }
    )

    return {
        "review": decision,
    }


def review_router(
    state: TravelState,
) -> str:
    """
    Route human decisions.

    approve -> finalize
    reject  -> planner revision
    modify  -> planner revision
    """

    review = state.get(
        "review",
        {},
    )

    action = review.get(
        "action",
        "",
    ).lower()

    if action == "approve":
        return "approve"

    if action in {
        "reject",
        "modify",
    }:
        return "revise"

    return "revise"


def revision_node(
    state: TravelState,
) -> dict:
    """
    Increment revision counter before
    sending the workflow back to planner.
    """

    return {
        "revision_count": (
            state.get(
                "revision_count",
                0,
            )
            + 1
        ),
        "status": "revising",
    }


def finalize_plan(
    state: TravelState,
) -> dict:
    """
    Finalize only after human approval.
    """

    return {
        "final": state.get(
            "draft",
            {},
        ),
        "status": "approved",
    }


# --------------------------------------------------
# LangGraph workflow
# --------------------------------------------------

builder = StateGraph(
    TravelState
)

builder.add_node(
    "research_agent",
    research_agent,
)

builder.add_node(
    "planner_agent",
    planner_agent,
)

builder.add_node(
    "human_review",
    human_review,
)

builder.add_node(
    "revision",
    revision_node,
)

builder.add_node(
    "finalize",
    finalize_plan,
)


# Workflow:
#
# START
#   |
# Research Agent
#   |
# Planner Agent
#   |
# Human Review
#   |
#   +---- Approve ----> Finalize ---> END
#   |
#   +---- Reject/Modify
#             |
#          Revision
#             |
#          Planner
#             |
#       Human Review again


builder.add_edge(
    START,
    "research_agent",
)

builder.add_edge(
    "research_agent",
    "planner_agent",
)

builder.add_edge(
    "planner_agent",
    "human_review",
)

builder.add_conditional_edges(
    "human_review",
    review_router,
    {
        "approve": "finalize",
        "revise": "revision",
    },
)

builder.add_edge(
    "revision",
    "planner_agent",
)

builder.add_edge(
    "finalize",
    END,
)


# SQLite persistence keeps LangGraph state
# across API requests and application restarts.
sqlite_connection = sqlite3.connect(
    "travel_planner.db",
    check_same_thread=False,
)

checkpointer = SqliteSaver(
    sqlite_connection
)

graph = builder.compile(
    checkpointer=checkpointer
)


def graph_config(
    plan_id: str,
) -> dict:
    """
    Each travel plan uses its own
    LangGraph thread.
    """

    return {
        "configurable": {
            "thread_id": plan_id
        }
    }


def start_plan(
    plan_id: str,
    request: dict,
):
    """
    Start a new travel planning workflow.
    """

    initial_state: TravelState = {
        "plan_id": plan_id,
        "request": request,
        "status": "started",
        "revision_count": 0,
    }

    return graph.invoke(
        initial_state,
        config=graph_config(
            plan_id
        ),
    )


def resume_plan(
    plan_id: str,
    review: dict,
):
    """
    Resume a paused HITL workflow
    with the human review decision.
    """

    return graph.invoke(
        Command(
            resume=review
        ),
        config=graph_config(
            plan_id
        ),
    )


def snapshot(
    plan_id: str,
):
    """
    Retrieve the current state
    of a travel plan.
    """

    return graph.get_state(
        graph_config(
            plan_id
        )
    )