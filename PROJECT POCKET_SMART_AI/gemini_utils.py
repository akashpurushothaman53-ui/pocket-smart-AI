"""
gemini_utils.py - Gemini AI Integration & Recommendation Engine for PocketSmart AI
Handles prompt orchestration, multimodal input (text & images), dynamic shopping link generation,
and intelligent fallback recommendations.
"""

import os
import re
import json
import logging
import urllib.parse
from typing import Dict, Any, Optional, List, Union
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fetch API Key
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

# Initialize Gemini Client / Model
genai_available = False
client = None
model_instance = None

try:
    if API_KEY and API_KEY.strip() and API_KEY != "your_gemini_api_key_here":
        import google.generativeai as genai
        genai.configure(api_key=API_KEY)
        # Prefer gemini-1.5-flash as documented, with gemini-2.0-flash / gemini-1.5-pro compatibility
        model_instance = genai.GenerativeModel("gemini-1.5-flash")
        genai_available = True
        logger.info("Successfully initialized google.generativeai with model gemini-1.5-flash")
except Exception as e:
    logger.warning(f"Could not initialize google.generativeai: {e}")

try:
    if not genai_available and API_KEY and API_KEY.strip() and API_KEY != "your_gemini_api_key_here":
        from google import genai as google_genai
        client = google_genai.Client(api_key=API_KEY)
        genai_available = True
        logger.info("Successfully initialized google-genai client")
except Exception as e:
    logger.warning(f"Could not initialize google.genai: {e}")


def usd_to_inr(amount_usd: float, exchange_rate: float = 83.0) -> float:
    """Convert USD amount to INR using the specified exchange rate."""
    return round(amount_usd * exchange_rate, 2)


def extract_json_from_response(text: str) -> Dict[str, Any]:
    """
    Robustly extract and parse JSON object from LLM response text,
    stripping markdown fences or surrounding narrative text.
    """
    if not text:
        raise ValueError("Empty response received from AI model.")

    # Remove markdown code block fences if present
    cleaned = text.strip()
    if "```json" in cleaned:
        cleaned = re.search(r"```json\s*(.*?)\s*```", cleaned, re.DOTALL).group(1)
    elif "```" in cleaned:
        cleaned = re.search(r"```\s*(.*?)\s*```", cleaned, re.DOTALL).group(1)

    # Attempt direct json load
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback to finding the first { and the last }
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise ValueError("Could not extract a valid JSON object from model output.")


# ---------------------------------------------------------------------------
# 1. HOME INTERIOR RECOMMENDATIONS
# ---------------------------------------------------------------------------

def get_home_recommendations(budget_input: Any) -> Dict[str, Any]:
    """
    Generate home interior recommendations within budget for Indian market.
    Matches the schema and logic specified in Activity 2.2 / 3.1.
    """
    # Normalize input whether Pydantic model or dict
    if hasattr(budget_input, "dict"):
        data = budget_input.dict()
    elif isinstance(budget_input, dict):
        data = budget_input
    else:
        data = {
            "total_budget": float(getattr(budget_input, "total_budget", 5000)),
            "num_lights": int(getattr(budget_input, "num_lights", 4)),
            "num_fans": int(getattr(budget_input, "num_fans", 2)),
            "num_furniture": int(getattr(budget_input, "num_furniture", 2)),
            "num_dining_tables": int(getattr(budget_input, "num_dining_tables", 1)),
            "has_living_room": bool(getattr(budget_input, "has_living_room", True)),
            "has_kitchen": bool(getattr(budget_input, "has_kitchen", True)),
            "has_bedroom": bool(getattr(budget_input, "has_bedroom", True)),
            "additional_requirements": str(getattr(budget_input, "additional_requirements", "") or "None"),
        }

    total_budget = float(data.get("total_budget", 5000.0))
    num_lights = int(data.get("num_lights", 0))
    num_fans = int(data.get("num_fans", 0))
    num_furniture = int(data.get("num_furniture", 0))
    num_dining_tables = int(data.get("num_dining_tables", 0))
    has_living_room = bool(data.get("has_living_room", True))
    has_kitchen = bool(data.get("has_kitchen", False))
    has_bedroom = bool(data.get("has_bedroom", False))
    additional_req = data.get("additional_requirements") or "None"

    # Rooms list
    rooms = []
    if has_living_room:
        rooms.append("Living Room")
    if has_kitchen:
        rooms.append("Kitchen")
    if has_bedroom:
        rooms.append("Bedroom")
    rooms_str = ", ".join(rooms) if rooms else "General Living Area"

    prompt = f"""
I need interior design product recommendations for a home in India with a total budget of ₹{total_budget:.2f}.
Requirements:
- {num_lights} lights/lighting fixtures
- {num_fans} ceiling fans
- {num_furniture} key furniture pieces
- {num_dining_tables} dining tables

Additional rooms to consider:
{rooms_str}

Additional requirements: {additional_req}

Please provide a detailed budget breakdown with product recommendations **available in India**.
Use **Indian brands and pricing**. Include **search terms** suitable for Indian shopping platforms.

Format your response strictly as JSON with the following structure:
{{
  "total_budget": {total_budget:.2f},
  "budget_breakdown": [
    {{
      "category": "Lighting",
      "allocation": 1500.0,
      "items": [
        {{
          "name": "LED Warm White Fixture",
          "description": "Energy-efficient ceiling mounted ambient lighting.",
          "estimated_price": 300.0,
          "quantity": {num_lights if num_lights > 0 else 1},
          "search_terms": "led ceiling fixture warm white"
        }}
      ]
    }}
  ],
  "calculation_table": [
    {{
      "category": "Lighting",
      "items_count": {num_lights if num_lights > 0 else 1},
      "total_cost": 300.0,
      "percentage_of_budget": 6.0
    }}
  ],
  "remaining_budget": 0.0,
  "additional_suggestions": [
    "Consider purchasing used furniture for further cost savings.",
    "Look for sales and discounts on online marketplaces.",
    "Prioritize essential items and postpone non-essential purchases."
  ]
}}
Ensure total costs stay within budget. Include search terms for each item to find on shopping websites like Flipkart, Amazon India, IKEA India.
"""

    result = None
    if genai_available:
        try:
            if model_instance:
                response = model_instance.generate_content(prompt)
                result = extract_json_from_response(response.text)
            elif client:
                res = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
                result = extract_json_from_response(res.text)
        except Exception as err:
            logger.error(f"Gemini API error during home recommendations: {err}")

    # Fallback if AI call failed or no API key configured
    if not result:
        result = _generate_fallback_home_recommendations(
            total_budget=total_budget,
            num_lights=num_lights,
            num_fans=num_fans,
            num_furniture=num_furniture,
            num_dining_tables=num_dining_tables,
            rooms=rooms,
            additional_req=additional_req
        )

    # Attach dynamic shopping links as documented in Activity 2.2 (page 12)
    for category in result.get("budget_breakdown", []):
        for item in category.get("items", []):
            search_terms = item.get("search_terms") or item.get("name", "home decor")
            encoded_query = urllib.parse.quote_plus(search_terms)
            item["shopping_links"] = {
                "amazon": f"https://www.amazon.in/s?k={encoded_query}",
                "flipkart": f"https://www.flipkart.com/search?q={encoded_query}",
                "ikea": f"https://www.ikea.com/in/en/search/?q={encoded_query}",
                "myntra": f"https://www.myntra.com/search?q={encoded_query}",
                "ajio": f"https://www.ajio.com/search/?text={encoded_query}"
            }

    # Ensure calculation table is populated and accurate
    if not result.get("calculation_table"):
        calc_table = []
        for cat in result.get("budget_breakdown", []):
            cat_name = cat.get("category", "General")
            items = cat.get("items", [])
            total_cat_cost = sum(it.get("estimated_price", 0) * it.get("quantity", 1) for it in items)
            pct = round((total_cat_cost / total_budget) * 100, 1) if total_budget > 0 else 0
            calc_table.append({
                "category": cat_name,
                "items_count": sum(it.get("quantity", 1) for it in items),
                "total_cost": round(total_cat_cost, 2),
                "percentage_of_budget": pct
            })
        result["calculation_table"] = calc_table

    return result


def _generate_fallback_home_recommendations(
    total_budget: float,
    num_lights: int,
    num_fans: int,
    num_furniture: int,
    num_dining_tables: int,
    rooms: List[str],
    additional_req: str
) -> Dict[str, Any]:
    """Generates realistic, budget-conscious fallback data if Gemini API is offline."""
    n_lights = max(num_lights, 2) if num_lights > 0 else 2
    n_fans = max(num_fans, 1) if num_fans > 0 else 1
    n_furn = max(num_furniture, 1) if num_furniture > 0 else 1
    n_dining = max(num_dining_tables, 1) if num_dining_tables > 0 else 0

    alloc_lights = round(total_budget * 0.15, 2)
    alloc_fans = round(total_budget * 0.25, 2)
    alloc_furn = round(total_budget * 0.40, 2)
    alloc_dining = round(total_budget * 0.15, 2) if n_dining > 0 else 0.0

    unit_light = round(alloc_lights / n_lights, 2)
    unit_fan = round(alloc_fans / n_fans, 2)
    unit_furn = round(alloc_furn / n_furn, 2)
    unit_dining = round(alloc_dining, 2) if n_dining > 0 else 0.0

    budget_breakdown = [
        {
            "category": "Lighting",
            "allocation": alloc_lights,
            "items": [
                {
                    "name": "Philips / Crompton LED Bulbs & Fixtures Pack",
                    "description": "Energy-efficient warm white illumination suitable for living and study spaces.",
                    "estimated_price": unit_light,
                    "quantity": n_lights,
                    "search_terms": "philips warm white led fixture bulb pack"
                }
            ]
        },
        {
            "category": "Ceiling Fans",
            "allocation": alloc_fans,
            "items": [
                {
                    "name": "Havells / Atomberg BLDC Energy Saver Ceiling Fan",
                    "description": "5-star rated, whisper-quiet airflow with remote control functionality.",
                    "estimated_price": unit_fan,
                    "quantity": n_fans,
                    "search_terms": "atomberg bldc ceiling fan energy saver"
                }
            ]
        },
        {
            "category": "Furniture",
            "allocation": alloc_furn,
            "items": [
                {
                    "name": "Compact Engineered Wood Modular Storage / Seating",
                    "description": "Minimalist, ergonomic multi-purpose unit with durable melamine finish.",
                    "estimated_price": unit_furn,
                    "quantity": n_furn,
                    "search_terms": "engineered wood modular shelf chair living room"
                }
            ]
        }
    ]

    if n_dining > 0:
        budget_breakdown.append({
            "category": "Dining Furniture",
            "allocation": alloc_dining,
            "items": [
                {
                    "name": "Foldable / Compact Solid Wood 4-Seater Dining Set",
                    "description": "Space-optimizing dining table with matching stackable chairs.",
                    "estimated_price": unit_dining,
                    "quantity": 1,
                    "search_terms": "compact 4 seater dining table set"
                }
            ]
        })

    total_spent = (unit_light * n_lights) + (unit_fan * n_fans) + (unit_furn * n_furn) + (unit_dining * (1 if n_dining > 0 else 0))
    remaining = max(0.0, round(total_budget - total_spent, 2))

    calc_table = []
    for cat in budget_breakdown:
        items = cat["items"]
        cat_cost = sum(i["estimated_price"] * i["quantity"] for i in items)
        calc_table.append({
            "category": cat["category"],
            "items_count": sum(i["quantity"] for i in items),
            "total_cost": round(cat_cost, 2),
            "percentage_of_budget": round((cat_cost / total_budget) * 100, 1) if total_budget > 0 else 0
        })

    return {
        "total_budget": total_budget,
        "budget_breakdown": budget_breakdown,
        "calculation_table": calc_table,
        "remaining_budget": remaining,
        "additional_suggestions": [
            "Consider purchasing refurbished or modular furniture for further cost efficiency.",
            "Look out for festive discounts and bundle deals on Amazon and Flipkart.",
            "Use warm lighting strips to give rooms a luxurious ambient feel on a tight budget."
        ]
    }


# ---------------------------------------------------------------------------
# 2. PARTY BUDGET RECOMMENDATIONS
# ---------------------------------------------------------------------------

def get_party_recommendations(budget_input: Any) -> Dict[str, Any]:
    """
    Generate party planning recommendations within budget for Indian market.
    Matches Activity 2.2 / 3.1 (pages 13-16).
    """
    if hasattr(budget_input, "dict"):
        data = budget_input.dict()
    elif isinstance(budget_input, dict):
        data = budget_input
    else:
        data = {
            "total_budget": float(getattr(budget_input, "total_budget", 5000)),
            "party_type": str(getattr(budget_input, "party_type", "Birthday")),
            "num_guests": int(getattr(budget_input, "num_guests", 15)),
            "venue_type": str(getattr(budget_input, "venue_type", "Home")),
            "needs_catering": bool(getattr(budget_input, "needs_catering", True)),
            "needs_decoration": bool(getattr(budget_input, "needs_decoration", True)),
            "needs_entertainment": bool(getattr(budget_input, "needs_entertainment", True)),
            "additional_requirements": str(getattr(budget_input, "additional_requirements", "") or "None"),
        }

    total_budget = float(data.get("total_budget", 5000.0))
    party_type = data.get("party_type", "Birthday")
    num_guests = int(data.get("num_guests", 10))
    venue_type = data.get("venue_type", "Home")
    needs_catering = bool(data.get("needs_catering", True))
    needs_decoration = bool(data.get("needs_decoration", True))
    needs_entertainment = bool(data.get("needs_entertainment", True))
    additional_req = data.get("additional_requirements") or "None"

    prompt = f"""
I need party planning recommendations for India with a total budget of ₹{total_budget:.2f}.

Party details:
- Type: {party_type}
- Number of guests: {num_guests}
- Venue type: {venue_type}
- Catering needed: {"Yes" if needs_catering else "No"}
- Decoration needed: {"Yes" if needs_decoration else "No"}
- Entertainment needed: {"Yes" if needs_entertainment else "No"}

Additional requirements: {additional_req}

Please provide a detailed budget breakdown with specific recommendations available in India using INR prices.
Use Indian brands, services, and typical cost expectations.

Format your response strictly as JSON with the following structure:
{{
  "total_budget": {total_budget:.2f},
  "budget_breakdown": [
    {{
      "category": "venue",
      "allocation": 1000.0,
      "items": [
        {{
          "name": "Community Hall / Venue Fee",
          "description": "Space rental or home arrangement supplies.",
          "estimated_price": 500.0,
          "quantity": 1,
          "search_terms": "party venue rental"
        }}
      ]
    }}
  ],
  "venue_suggestions": [
    {{
      "name": "Local Banquet / Community Terrace",
      "type": "Residential / Event Hall",
      "capacity": {num_guests + 10},
      "estimated_cost": 0.0,
      "search_terms": "party venue halls"
    }}
  ],
  "remaining_budget": 0.0,
  "additional_suggestions": [
    "Consider making the meal a potluck style or buffet to reduce catering costs.",
    "Look for party bundle packs online for decorations.",
    "Curate a Spotify party playlist rather than hiring a commercial DJ."
  ]
}}
Ensure all costs are in INR and total does not exceed the given budget.
Provide search terms suitable for Indian websites such as BookMyShow, Swiggy, Zomato, Flipkart, etc.
"""

    result = None
    if genai_available:
        try:
            if model_instance:
                response = model_instance.generate_content(prompt)
                result = extract_json_from_response(response.text)
            elif client:
                res = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
                result = extract_json_from_response(res.text)
        except Exception as err:
            logger.error(f"Gemini API error during party recommendations: {err}")

    if not result:
        result = _generate_fallback_party_recommendations(
            total_budget=total_budget,
            party_type=party_type,
            num_guests=num_guests,
            venue_type=venue_type,
            needs_catering=needs_catering,
            needs_decoration=needs_decoration,
            needs_entertainment=needs_entertainment,
            additional_req=additional_req
        )

    # Calculation table INR creation as per Activity 2.2 (page 14)
    result["calculation_table_inr"] = []
    categories: Dict[str, Dict[str, Any]] = {}

    for cat in result.get("budget_breakdown", []):
        cat_name = cat.get("category", "Misc")
        cat_allocation = cat.get("allocation", 0)

        if cat_name not in categories:
            categories[cat_name] = {
                "category": cat_name,
                "items_count": 0,
                "total_cost": 0,
                "percentage_of_budget": 0
            }

        for item in cat.get("items", []):
            qty = item.get("quantity", 1)
            categories[cat_name]["items_count"] += qty
            categories[cat_name]["total_cost"] += (item.get("estimated_price", 0) * qty)

        if result.get("total_budget", 0) > 0:
            categories[cat_name]["percentage_of_budget"] = round(
                (categories[cat_name]["total_cost"] / result["total_budget"]) * 100, 1
            )

    for cat_data in categories.values():
        result["calculation_table_inr"].append(cat_data)

    # Platform mapping from Activity 2.2 (page 15)
    category_platforms = {
        "venue": ["google", "booking", "makemytrip", "oyorooms", "nobroker"],
        "catering": ["swiggy", "zomato"],
        "food": ["swiggy", "zomato", "bigbasket", "amazon", "flipkart"],
        "drinks": ["swiggy", "zomato", "bigbasket", "amazon", "flipkart"],
        "decoration": ["amazon", "flipkart", "meesho", "myntra"],
        "entertainment": ["bookmyshow", "amazon", "flipkart"],
        "gifts": ["amazon", "flipkart", "myntra", "meesho"],
        "photography": ["google", "amazon", "flipkart"],
        "music": ["amazon", "flipkart", "bookmyshow"],
        "games": ["amazon", "flipkart"],
        "accessories": ["amazon", "flipkart", "myntra", "meesho"],
        "transportation": ["makemytrip", "google"],
        "return_gifts": ["amazon", "flipkart", "myntra", "meesho"],
        "contingency": ["amazon", "flipkart", "google"]
    }
    default_platforms = ["amazon", "flipkart", "google"]

    # Link generation for budget breakdown items (Activity 2.2, page 15)
    for category in result.get("budget_breakdown", []):
        cat_name = category.get("category", "").lower()
        relevant_platforms = category_platforms.get(cat_name, default_platforms)

        for item in category.get("items", []):
            search_terms = item.get("search_terms") or item.get("name", "party items")
            encoded_query = urllib.parse.quote_plus(search_terms)
            shopping_links = {}

            if "amazon" in relevant_platforms:
                shopping_links["amazon"] = f"https://www.amazon.in/s?k={encoded_query}"
            if "flipkart" in relevant_platforms:
                shopping_links["flipkart"] = f"https://www.flipkart.com/search?q={encoded_query}"
            if "bigbasket" in relevant_platforms:
                shopping_links["bigbasket"] = f"https://www.bigbasket.com/ps/?q={encoded_query}"
            if "swiggy" in relevant_platforms:
                shopping_links["swiggy"] = f"https://www.swiggy.com/search?query={encoded_query}"
            if "zomato" in relevant_platforms:
                shopping_links["zomato"] = f"https://www.zomato.com/search?q={encoded_query}"
            if "bookmyshow" in relevant_platforms:
                shopping_links["bookmyshow"] = f"https://in.bookmyshow.com/search?q={encoded_query}"
            if "myntra" in relevant_platforms:
                shopping_links["myntra"] = f"https://www.myntra.com/search?q={encoded_query}"
            if "meesho" in relevant_platforms:
                shopping_links["meesho"] = f"https://www.meesho.com/search?q={encoded_query}"
            if "google" in relevant_platforms:
                shopping_links["google"] = f"https://www.google.com/search?q={encoded_query}"
            if "booking" in relevant_platforms:
                shopping_links["booking"] = f"https://www.booking.com/search.html?ss={encoded_query}"
            if "makemytrip" in relevant_platforms:
                shopping_links["makemytrip"] = f"https://www.makemytrip.com/hotels/hotel-listing/?searchtext={encoded_query}"
            if "oyorooms" in relevant_platforms:
                shopping_links["oyorooms"] = f"https://www.oyorooms.com/search/?location={encoded_query}"
            if "nobroker" in relevant_platforms:
                shopping_links["nobroker"] = f"https://www.nobroker.in/property/search?searchterm={encoded_query}"

            item["shopping_links"] = shopping_links

    # Link generation for venue suggestions (Activity 2.2, page 16)
    venue_platforms = ["google", "booking", "makemytrip", "oyorooms", "nobroker"]
    for venue in result.get("venue_suggestions", []):
        search_terms = venue.get("search_terms") or venue.get("name", "party venue")
        encoded_query = urllib.parse.quote_plus(search_terms)
        v_links = {}
        if "google" in venue_platforms:
            v_links["google"] = f"https://www.google.com/search?q={encoded_query}"
        if "booking" in venue_platforms:
            v_links["booking"] = f"https://www.booking.com/search.html?ss={encoded_query}"
        if "makemytrip" in venue_platforms:
            v_links["makemytrip"] = f"https://www.makemytrip.com/hotels/hotel-listing/?searchtext={encoded_query}"
        if "oyorooms" in venue_platforms:
            v_links["oyorooms"] = f"https://www.oyorooms.com/search/?location={encoded_query}"
        if "nobroker" in venue_platforms:
            v_links["nobroker"] = f"https://www.nobroker.in/property/search?searchterm={encoded_query}"
        venue["search_links"] = v_links

    return result


def _generate_fallback_party_recommendations(
    total_budget: float,
    party_type: str,
    num_guests: int,
    venue_type: str,
    needs_catering: bool,
    needs_decoration: bool,
    needs_entertainment: bool,
    additional_req: str
) -> Dict[str, Any]:
    """Generates intelligent party budget allocation fallback data."""
    budget_breakdown = []

    # Allocate proportions
    catering_cost = round(total_budget * 0.45, 2) if needs_catering else 0.0
    decor_cost = round(total_budget * 0.20, 2) if needs_decoration else 0.0
    entertain_cost = round(total_budget * 0.15, 2) if needs_entertainment else 0.0
    venue_cost = round(total_budget * 0.10, 2) if venue_type.lower() != "home" else 0.0
    contingency_cost = round(total_budget * 0.10, 2)

    if venue_cost > 0:
        budget_breakdown.append({
            "category": "venue",
            "allocation": venue_cost,
            "items": [
                {
                    "name": f"{venue_type} Reservation / Booking Deposit",
                    "description": f"Space booking suitable for {num_guests} guests.",
                    "estimated_price": venue_cost,
                    "quantity": 1,
                    "search_terms": f"party hall rental {venue_type}"
                }
            ]
        })
    else:
        budget_breakdown.append({
            "category": "venue",
            "allocation": 0.0,
            "items": [
                {
                    "name": "Home Venue Setup",
                    "description": "Utilizing living/terrace area as event venue.",
                    "estimated_price": 0.0,
                    "quantity": 1,
                    "search_terms": "party setup home living room"
                }
            ]
        })

    if needs_catering:
        per_head = round(catering_cost / max(num_guests, 1), 2)
        budget_breakdown.append({
            "category": "catering",
            "allocation": catering_cost,
            "items": [
                {
                    "name": f"Gourmet Meal & Snack Combo ({party_type})",
                    "description": f"Custom meal catering for {num_guests} people with drinks and desserts.",
                    "estimated_price": per_head,
                    "quantity": num_guests,
                    "search_terms": f"party snacks meal catering bulk order"
                }
            ]
        })

    if needs_decoration:
        budget_breakdown.append({
            "category": "decoration",
            "allocation": decor_cost,
            "items": [
                {
                    "name": f"{party_type} Theme Balloons & Backdrop Kit",
                    "description": "Complete DIY decorative arch, fairy lights, and themed banner.",
                    "estimated_price": decor_cost,
                    "quantity": 1,
                    "search_terms": f"{party_type} celebration theme balloon arch kit"
                }
            ]
        })

    if needs_entertainment:
        half_ent = round(entertain_cost / 2, 2)
        budget_breakdown.append({
            "category": "entertainment",
            "allocation": entertain_cost,
            "items": [
                {
                    "name": "Bluetooth Party Speaker & Mic Rental / Purchase",
                    "description": "High-bass party audio with karaoke microphone for music & games.",
                    "estimated_price": half_ent,
                    "quantity": 1,
                    "search_terms": "portable bluetooth party speaker with mic"
                },
                {
                    "name": "Party Board Games & Activity Props",
                    "description": "Engaging interactive games suitable for group enjoyment.",
                    "estimated_price": half_ent,
                    "quantity": 1,
                    "search_terms": "party games for groups fun board games"
                }
            ]
        })

    budget_breakdown.append({
        "category": "contingency",
        "allocation": contingency_cost,
        "items": [
            {
                "name": "Emergency & Miscellaneous Supplies",
                "description": "Buffer for disposable tableware, extra ice, and last-minute needs.",
                "estimated_price": contingency_cost,
                "quantity": 1,
                "search_terms": "biodegradable disposable party tableware pack"
            }
        ]
    })

    spent = sum(cat["allocation"] for cat in budget_breakdown)
    remaining = max(0.0, round(total_budget - spent, 2))

    return {
        "total_budget": total_budget,
        "budget_breakdown": budget_breakdown,
        "venue_suggestions": [
            {
                "name": f"{venue_type} / Community Gathering Center",
                "type": "Residential / Event Hall",
                "capacity": num_guests + 10,
                "estimated_cost": venue_cost,
                "search_terms": f"community hall {venue_type} near me"
            }
        ],
        "remaining_budget": remaining,
        "additional_suggestions": [
            "Consider ordering snacks in bulk through Swiggy Gourmet or Zomato Legends for premium curation.",
            "Use pre-made photo booth printouts to let guests take memorable pictures without renting expensive booths.",
            "Prepare a collaborative Spotify or YouTube playlist for guest participation."
        ]
    }


# ---------------------------------------------------------------------------
# 3. JEWELRY BUDGET RECOMMENDATIONS (MULTIMODAL)
# ---------------------------------------------------------------------------

def get_jewelry_recommendations(budget_input: Any, image_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate jewelry recommendations based on occasion, style preferences,
    and optional uploaded outfit image.
    Matches Activity 2.2 / 3.1 (pages 16-17).
    """
    if hasattr(budget_input, "dict"):
        data = budget_input.dict()
    elif isinstance(budget_input, dict):
        data = budget_input
    else:
        data = {
            "total_budget": float(getattr(budget_input, "total_budget", 5000)),
            "occasion": str(getattr(budget_input, "occasion", "Wedding")),
            "preferences": str(getattr(budget_input, "preferences", "") or "Not specified")
        }

    total_budget = float(data.get("total_budget", 5000.0))
    occasion = data.get("occasion", "Wedding")
    preferences = data.get("preferences") or "Not specified"

    base_prompt = f"""
I need jewelry recommendations for India with a total budget of ₹{total_budget:.2f}.

Occasion: {occasion}
Preferences: {preferences}
Provide only India-relevant styles, availability, and price ranges in INR.
"""

    result = None
    img_object = None

    if image_path and os.path.exists(image_path):
        try:
            img_object = Image.open(image_path)
        except Exception as e:
            logger.warning(f"Failed to open uploaded outfit image: {e}")

    if img_object is not None:
        prompt = base_prompt + """
An image of the outfit is uploaded. Suggest jewelry that complements it, considering color, design, and occasion appropriateness.

Format the output as JSON:
{
  "outfit_analysis": {
    "colors": ["Primary Color", "Secondary Color"],
    "style": "Traditional / Western / Indo-Western",
    "formality": "Festive / Formal / Casual"
  },
  "total_budget": 5000.0,
  "jewelry_recommendations": [
    {
      "item_type": "Necklace / Earring / Bracelet / Ring / Watch",
      "description": "Specific accessory description complementing outfit neckline/tones.",
      "style": "Matching style tone",
      "estimated_price": 1500.0,
      "search_terms": "search query for Indian jewelry stores"
    }
  ],
  "remaining_budget": 500.0,
  "styling_tips": [
    "Keep earrings lightweight if wearing an elaborate necklace.",
    "Match metal finish with the outfit zari or embroidery work."
  ]
}
Keep prices in INR and stay within budget.
Include Indian-friendly search terms for shopping.
"""
        if genai_available:
            try:
                if model_instance:
                    response = model_instance.generate_content([prompt, img_object])
                    result = extract_json_from_response(response.text)
                elif client:
                    res = client.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=[prompt, img_object]
                    )
                    result = extract_json_from_response(res.text)
            except Exception as err:
                logger.error(f"Multimodal Gemini call error: {err}")
    else:
        prompt = base_prompt + """
Format the output as JSON:
{
  "outfit_analysis": {
    "colors": ["Coordinated classic palette"],
    "style": "Contemporary Elegant",
    "formality": "Occasion-specific"
  },
  "total_budget": 5000.0,
  "jewelry_recommendations": [
    {
      "item_type": "Bracelet / Ring / Earrings / Watch",
      "description": "Detailed description of the jewelry item.",
      "style": "Style category",
      "estimated_price": 1000.0,
      "search_terms": "product search keywords"
    }
  ],
  "remaining_budget": 0.0,
  "styling_tips": [
    "Choose one statement piece to draw attention.",
    "Coordinate metal tones across rings and watch bands."
  ]
}
Keep prices in INR and relevant to Indian brands.
"""
        if genai_available:
            try:
                if model_instance:
                    response = model_instance.generate_content(prompt)
                    result = extract_json_from_response(response.text)
                elif client:
                    res = client.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=prompt
                    )
                    result = extract_json_from_response(res.text)
            except Exception as err:
                logger.error(f"Text-only Gemini call error: {err}")

    # Fallback if AI is offline
    if not result:
        result = _generate_fallback_jewelry_recommendations(
            total_budget=total_budget,
            occasion=occasion,
            preferences=preferences,
            has_image=img_object is not None
        )

    # Add shopping links for each jewelry item (Activity 2.2, page 17)
    for item in result.get("jewelry_recommendations", []):
        search_terms = item.get("search_terms") or item.get("item_type", "jewelry")
        encoded_query = urllib.parse.quote_plus(search_terms)
        item["shopping_links"] = {
            "amazon": f"https://www.amazon.in/s?k={encoded_query}",
            "flipkart": f"https://www.flipkart.com/search?q={encoded_query}",
            "bluestone": f"https://www.bluestone.com/search.html?query={encoded_query}",
            "tanishq": f"https://www.tanishq.co.in/search?q={encoded_query}",
            "caratlane": f"https://www.caratlane.com/search?q={encoded_query}",
            "melorra": f"https://www.melorra.com/search?q={encoded_query}",
            "meesho": f"https://www.meesho.com/search?q={encoded_query}"
        }

    return result


def _generate_fallback_jewelry_recommendations(
    total_budget: float,
    occasion: str,
    preferences: str,
    has_image: bool = False
) -> Dict[str, Any]:
    """Generates realistic jewelry recommendation fallback data."""
    price_b1 = round(total_budget * 0.15, 2)
    price_b2 = round(total_budget * 0.20, 2)
    price_b3 = round(total_budget * 0.50, 2)
    remaining = max(0.0, round(total_budget - (price_b1 + price_b2 + price_b3), 2))

    return {
        "outfit_analysis": {
            "colors": ["Royal Blue", "Warm Gold"] if has_image else ["Classic Metallic", "Neutral"],
            "style": "Elegant Festive" if "wedding" in occasion.lower() else "Contemporary Chic",
            "formality": "Formal / Celebration" if "wedding" in occasion.lower() else "Semi-Formal"
        },
        "total_budget": total_budget,
        "jewelry_recommendations": [
            {
                "item_type": "Bracelet",
                "description": f"A refined link or cuff bracelet with subtle polish. Complements {occasion} attire without overwhelming.",
                "style": "Minimalist Accent",
                "estimated_price": price_b1,
                "search_terms": f"{occasion} stylish cuff bracelet"
            },
            {
                "item_type": "Ring",
                "description": "Silver-toned / rose-gold adjustable statement ring with cubic zirconia detailing.",
                "style": "Sophisticated",
                "estimated_price": price_b2,
                "search_terms": "sterling silver cubic zirconia ring"
            },
            {
                "item_type": "Watch / Pendant",
                "description": f"Classic slim analog watch or delicate pendant necklace selected for {occasion}.",
                "style": "Timeless",
                "estimated_price": price_b3,
                "search_terms": "classic analog dress watch gold finish"
            }
        ],
        "remaining_budget": remaining,
        "styling_tips": [
            f"Keep jewelry balanced to match the {occasion} mood effortlessly.",
            "Harmonize metal tones across accessories (rose gold, silver, or traditional yellow gold).",
            "A statement watch or choker serves as an elegant anchor piece."
        ]
    }
