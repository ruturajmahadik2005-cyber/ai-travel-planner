import os
from datetime import date

import requests


SERPER_URL = "https://google.serper.dev/search"


# ============================================================
# RESEARCH TOOL 1 - SERPER REAL-TIME WEB SEARCH
# ============================================================

def web_search(query: str, num: int = 6) -> list[dict]:
    api_key = os.getenv("SERPER_API_KEY")

    if not api_key:
        return [
            {
                "title": "Serper API key not configured",
                "snippet": (
                    f"Live research unavailable for: {query}"
                ),
                "link": None,
            }
        ]

    try:
        response = requests.post(
            SERPER_URL,
            headers={
                "X-API-KEY": api_key,
                "Content-Type": "application/json",
            },
            json={
                "q": query,
                "num": num,
            },
            timeout=20,
        )

        response.raise_for_status()

        organic = response.json().get("organic", [])

        return [
            {
                "title": item.get("title"),
                "snippet": item.get("snippet"),
                "link": item.get("link"),
            }
            for item in organic[:num]
        ]

    except requests.RequestException as error:
        return [
            {
                "title": "Search temporarily unavailable",
                "snippet": str(error),
                "link": None,
            }
        ]


# ============================================================
# RESEARCH TOOL 2 - TRAVEL WEATHER / SEASON TOOL
# ============================================================

def weather_tool(
    destination: str,
    start_date: date,
    end_date: date,
) -> dict:
    """
    Lightweight complementary travel-season tool.

    It does not invent an exact weather forecast.
    The Research Agent uses Serper for live destination
    information and this tool provides date-aware
    weather planning guidance.
    """

    month = start_date.strftime("%B")

    month_number = start_date.month

    if month_number in (12, 1, 2):
        general_guidance = (
            "Seasonal conditions can vary by destination. "
            "Carry suitable layers and verify the live "
            "forecast shortly before travel."
        )

    elif month_number in (3, 4, 5):
        general_guidance = (
            "Warm conditions may be possible depending on "
            "the destination. Carry sun protection, stay "
            "hydrated, and verify the live forecast before travel."
        )

    elif month_number in (6, 7, 8, 9):
        general_guidance = (
            "Rain or humid conditions may be possible depending "
            "on the destination. Carry light rain protection and "
            "keep indoor alternatives in the itinerary."
        )

    else:
        general_guidance = (
            "Weather can change during this travel period. "
            "Pack flexible layers and verify the live forecast "
            "shortly before departure."
        )

    return {
        "destination": destination,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "travel_month": month,
        "guidance": general_guidance,
        "recommendation": (
            "Use current web-search findings for destination-specific "
            "conditions and recheck the forecast close to departure."
        ),
        "tool": "Travel Season Advisor",
    }


# ============================================================
# PLANNER TOOL 1 - BUDGET ALLOCATOR
# ============================================================

def budget_allocator(
    budget_min: float,
    budget_max: float,
    travelers: int,
    days: int,
) -> dict:

    safe_days = max(1, days)
    safe_travelers = max(1, travelers)

    target_total = (budget_min + budget_max) / 2

    weights = {
        "lodging": 0.40,
        "food": 0.20,
        "activities": 0.18,
        "local_transport": 0.12,
        "buffer": 0.10,
    }

    allocation = {
        category: round(target_total * weight, 2)
        for category, weight in weights.items()
    }

    allocation.update(
        {
            "budget_min": round(budget_min, 2),
            "budget_max": round(budget_max, 2),
            "target_total": round(target_total, 2),
            "travelers": safe_travelers,
            "days": safe_days,
            "per_person": round(
                target_total / safe_travelers,
                2,
            ),
            "per_person_per_day": round(
                target_total
                / (safe_travelers * safe_days),
                2,
            ),
        }
    )

    return allocation


# ============================================================
# PLANNER TOOL 2 - PACKING ASSISTANT
# ============================================================

def packing_tool(
    interests: list[str],
    days: int,
) -> list[str]:

    safe_days = max(1, days)

    items = [
        "passport/ID and booking confirmations",
        "comfortable walking shoes",
        "weather-appropriate clothing",
        "phone charger and power bank",
        "basic medicines and personal care items",
        f"clothes for about {safe_days} days",
    ]

    interests_text = " ".join(interests).lower()

    if any(
        word in interests_text
        for word in [
            "hike",
            "hiking",
            "trek",
            "trekking",
            "nature",
        ]
    ):
        items.extend(
            [
                "daypack",
                "reusable water bottle",
                "comfortable outdoor footwear",
            ]
        )

    if any(
        word in interests_text
        for word in [
            "beach",
            "beaches",
            "swim",
            "swimming",
        ]
    ):
        items.extend(
            [
                "swimwear",
                "sunscreen",
                "sunglasses",
            ]
        )

    if any(
        word in interests_text
        for word in [
            "photography",
            "photos",
            "camera",
        ]
    ):
        items.extend(
            [
                "camera or phone storage",
                "extra charging cable",
            ]
        )

    return list(dict.fromkeys(items))