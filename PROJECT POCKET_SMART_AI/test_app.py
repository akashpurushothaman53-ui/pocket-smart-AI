"""
test_app.py - Automated End-to-End Test Suite for PocketSmart AI
Tests authentication, session management, and all 3 AI budget recommendation planners.
"""

import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from starlette.testclient import TestClient

# Ensure current directory is on python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import app, users_db, active_sessions, user_recommendations

client = TestClient(app)

def test_public_pages():
    print("\n--- Testing Public HTML Pages ---")
    res = client.get("/")
    assert res.status_code == 200, f"Expected 200 for '/', got {res.status_code}"
    assert "PocketSmart" in res.text
    print("✓ Landing page (/) loaded successfully")

    res = client.get("/login")
    assert res.status_code == 200
    assert "Welcome Back" in res.text
    print("✓ Login page (/login) loaded successfully")

    res = client.get("/register")
    assert res.status_code == 200
    assert "Create Your Account" in res.text
    print("✓ Register page (/register) loaded successfully")


def test_auth_and_session():
    print("\n--- Testing Authentication & Sessions ---")
    # Test seeded demo user login
    login_res = client.post("/login", data={"username": "sai", "password": "password123"})
    assert login_res.status_code == 200, f"Expected 200 for login, got {login_res.status_code}"
    login_data = login_res.json()
    assert "access_token" in login_data
    token = login_data["access_token"]
    print(f"✓ Login verified for 'sai'. Received token.")

    # Access protected dashboard
    dash_res = client.get("/dashboard", cookies={"access_token": f"Bearer {token}"})
    assert dash_res.status_code == 200
    assert "Welcome, Sai Kumar!" in dash_res.text or "Welcome, sai!" in dash_res.text
    print("✓ Dashboard accessible with authenticated token")

    # Session info endpoint
    session_res = client.get("/session-info", headers={"Authorization": f"Bearer {token}"})
    assert session_res.status_code == 200
    session_data = session_res.json()
    assert session_data["username"] == "sai"
    print("✓ Session info endpoint (/session-info) verified")


def test_home_budget_planner():
    print("\n--- Testing Home Interior Budget Planner ---")
    login_res = client.post("/login", data={"username": "sai", "password": "password123"})
    token = login_res.json()["access_token"]

    payload = {
        "total_budget": 5000.0,
        "num_lights": 5,
        "num_fans": 4,
        "num_furniture": 2,
        "num_dining_tables": 1,
        "has_living_room": True,
        "has_kitchen": True,
        "has_bedroom": True,
        "additional_requirements": "Warm contemporary Scandinavian theme"
    }

    res = client.post(
        "/home-budget",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200, f"Expected 200 for /home-budget, got {res.status_code}: {res.text}"
    data = res.json()

    assert "budget_breakdown" in data
    assert "calculation_table" in data
    assert "remaining_budget" in data
    assert "additional_suggestions" in data

    # Verify shopping links structure
    first_item = data["budget_breakdown"][0]["items"][0]
    assert "shopping_links" in first_item
    links = first_item["shopping_links"]
    assert "amazon" in links
    assert "flipkart" in links
    assert "ikea" in links
    print("✓ Home Budget Recommendations returned valid categories, items & shopping links")


def test_party_budget_planner():
    print("\n--- Testing Party Budget Planner ---")
    login_res = client.post("/login", data={"username": "sai", "password": "password123"})
    token = login_res.json()["access_token"]

    payload = {
        "total_budget": 5000.0,
        "party_type": "Wedding",
        "num_guests": 15,
        "venue_type": "Banquet Hall",
        "needs_catering": True,
        "needs_decoration": True,
        "needs_entertainment": True,
        "additional_requirements": "Vegetarian Indian buffet with live acoustic music"
    }

    res = client.post(
        "/party-budget",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200, f"Expected 200 for /party-budget, got {res.status_code}: {res.text}"
    data = res.json()

    assert "budget_breakdown" in data
    assert "calculation_table_inr" in data
    assert "additional_suggestions" in data

    # Verify party platforms
    has_catering = False
    for cat in data["budget_breakdown"]:
        if cat.get("category") == "catering":
            has_catering = True
            links = cat["items"][0].get("shopping_links", {})
            assert "swiggy" in links or "zomato" in links or "amazon" in links

    print("✓ Party Budget Recommendations returned valid categories, guest allocations & vendor links")


def test_jewelry_budget_planner():
    print("\n--- Testing Jewelry Budget Planner ---")
    login_res = client.post("/login", data={"username": "sai", "password": "password123"})
    token = login_res.json()["access_token"]

    data_payload = {
        "total_budget": 5000.0,
        "occasion": "Birthday",
        "preferences": "Minimalist silver or rose gold"
    }

    res = client.post(
        "/jewelry-budget",
        data=data_payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200, f"Expected 200 for /jewelry-budget, got {res.status_code}: {res.text}"
    data = res.json()

    assert "outfit_analysis" in data
    assert "jewelry_recommendations" in data
    assert "styling_tips" in data

    item = data["jewelry_recommendations"][0]
    links = item.get("shopping_links", {})
    assert "amazon" in links
    assert "bluestone" in links or "tanishq" in links
    print("✓ Jewelry Budget Recommendations returned valid styling analysis & jewelry catalog links")


def test_history_and_details():
    print("\n--- Testing History & Details API ---")
    login_res = client.post("/login", data={"username": "sai", "password": "password123"})
    token = login_res.json()["access_token"]

    hist_res = client.get("/recommendation-history", headers={"Authorization": f"Bearer {token}"})
    assert hist_res.status_code == 200
    history = hist_res.json()["history"]
    assert len(history) > 0
    first_id = history[0]["id"]
    print(f"✓ Recommendation history retrieved ({len(history)} items)")

    detail_res = client.get(f"/recommendation-details/{first_id}", headers={"Authorization": f"Bearer {token}"})
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == first_id
    assert "full_result" in detail
    print(f"✓ Recommendation details for ID #{first_id} verified")


if __name__ == "__main__":
    print("Starting PocketSmart AI Test Suite...")
    test_public_pages()
    test_auth_and_session()
    test_home_budget_planner()
    test_party_budget_planner()
    test_jewelry_budget_planner()
    test_history_and_details()
    print("\n==========================================")
    print("  ALL TESTS PASSED SUCCESSFULLY! (100%)   ")
    print("==========================================")
