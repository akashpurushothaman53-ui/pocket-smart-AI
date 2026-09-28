"""
app.py - PocketSmart AI: Your Smart Budget & Recommendation Assistant
FastAPI Backend Application with JWT Authentication, Session Management,
and AI-Powered Recommendation Endpoints.
"""

import os
import re
import uuid
import shutil
import asyncio
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Union

from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    File,
    UploadFile,
    Form,
    Request,
    status,
    Cookie
)
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import JWTError, jwt
from dotenv import load_dotenv

from gemini_utils import (
    get_home_recommendations,
    get_party_recommendations,
    get_jewelry_recommendations,
    usd_to_inr
)

# Load environment variables
load_dotenv()

# FastAPI app initialization (Activity 2.1)
app = FastAPI(
    title="PocketSmart: AI Budget Planner",
    description="Cross-platform budget allocation and recommendation system powered by Gemini AI",
    version="1.0.0"
)

# Security and Session Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "pocketsmart_ai_super_secret_jwt_key_2025_secure_token")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# Password hashing context (resilient bcrypt implementation compatible with all Python & bcrypt versions)
import bcrypt

class PasswordManager:
    """Modern bcrypt-based password manager supporting .hash() and .verify()"""
    def hash(self, secret: str) -> str:
        return bcrypt.hashpw(secret.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")

    def verify(self, secret: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(secret.encode("utf-8")[:72], hashed.encode("utf-8"))
        except Exception:
            return False

pwd_context = PasswordManager()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files and Templates Setup (Activity 2.1)
os.makedirs("static/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ---------------------------------------------------------------------------
# DATA MODELS & SCHEMAS
# ---------------------------------------------------------------------------

class RegisterUser(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class UserInDB(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    hashed_password: str
    disabled: Optional[bool] = False


class UserSession:
    def __init__(self, username: str, token: str, user_data: Optional[Dict[str, Any]] = None):
        now = datetime.now(timezone.utc)
        self.username = username
        self.login_time = now
        self.last_activity = now
        self.token = token
        self.user_data = user_data or {}


class HomeBudgetInput(BaseModel):
    total_budget: float
    num_lights: int = 0
    num_fans: int = 0
    num_furniture: int = 0
    num_dining_tables: int = 0
    has_living_room: bool = True
    has_kitchen: bool = False
    has_bedroom: bool = False
    additional_requirements: Optional[str] = None


class PartyBudgetInput(BaseModel):
    total_budget: float
    party_type: str = "Birthday"
    num_guests: int = 10
    venue_type: Optional[str] = "Home"
    needs_catering: bool = True
    needs_decoration: bool = True
    needs_entertainment: bool = True
    additional_requirements: Optional[str] = None


class JewelryBudgetInput(BaseModel):
    total_budget: float
    occasion: str = "Wedding"
    preferences: Optional[str] = None


class RecommendationItem:
    def __init__(
        self,
        id: str,
        timestamp: str,
        recommendation_type: str,
        input_summary: Dict[str, Any],
        result_summary: str,
        full_result: Dict[str, Any]
    ):
        self.id = id
        self.timestamp = timestamp
        self.recommendation_type = recommendation_type
        self.input_summary = input_summary
        self.result_summary = result_summary
        self.full_result = full_result


# ---------------------------------------------------------------------------
# IN-MEMORY DATABASE & STATE
# ---------------------------------------------------------------------------

users_db: Dict[str, UserInDB] = {}
active_sessions: Dict[str, UserSession] = {}
blacklisted_tokens: set = set()
user_recommendations: Dict[str, List[RecommendationItem]] = {}


def seed_default_user():
    """Seed default demo user 'sai' to match project demonstration examples."""
    hashed = pwd_context.hash("password123")
    demo_user = UserInDB(
        username="sai",
        email="sai@pocketsmart.ai",
        full_name="Sai Kumar",
        hashed_password=hashed
    )
    users_db["sai"] = demo_user

    # Pre-populate sample history for 'sai' matching page 31 & 38 in document
    user_recommendations["sai"] = [
        RecommendationItem(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(timezone.utc).strftime("%b %d, %Y, %I:%M %p"),
            recommendation_type="home",
            input_summary={
                "total_budget": 5000.0,
                "rooms": "Living Room, Kitchen",
                "lights": 5,
                "fans": 4,
                "furniture": 2
            },
            result_summary="Home Interior Plan: 5 Lights, 4 Fans, 2 Furniture pieces, Living Room & Kitchen within ₹5,000",
            full_result={
                "total_budget": 5000.0,
                "remaining_budget": 500.0,
                "budget_breakdown": [
                    {
                        "category": "Lighting",
                        "allocation": 1500.0,
                        "items": [
                            {
                                "name": "LED Bulb (Warm White)",
                                "description": "Energy-efficient LED bulbs for general lighting.",
                                "estimated_price": 100.0,
                                "quantity": 5,
                                "search_terms": "led bulb warm white pack",
                                "shopping_links": {
                                    "amazon": "https://www.amazon.in/s?k=led+bulb+warm+white+pack",
                                    "flipkart": "https://www.flipkart.com/search?q=led+bulb+warm+white+pack",
                                    "ikea": "https://www.ikea.com/in/en/search/?q=led+bulb+warm+white+pack",
                                    "myntra": "https://www.myntra.com/search?q=led+bulb+warm+white+pack",
                                    "ajio": "https://www.ajio.com/search/?text=led+bulb+warm+white+pack"
                                }
                            }
                        ]
                    }
                ],
                "calculation_table": [
                    {"category": "Lighting", "items_count": 5, "total_cost": 500.0, "percentage_of_budget": 10.0}
                ],
                "additional_suggestions": ["Consider purchasing used furniture for further cost savings."]
            }
        ),
        RecommendationItem(
            id=str(uuid.uuid4())[:8],
            timestamp=(datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%b %d, %Y, %I:%M %p"),
            recommendation_type="party",
            input_summary={
                "total_budget": 5000.0,
                "party_type": "Wedding",
                "guests": 3,
                "needs": ["Catering", "Entertainment"]
            },
            result_summary="Party Plan: Wedding celebration for 3 guests with Catering & Entertainment within ₹5,000",
            full_result={
                "total_budget": 5000.0,
                "remaining_budget": 0.0,
                "budget_breakdown": [
                    {
                        "category": "catering",
                        "allocation": 2000.0,
                        "items": [
                            {
                                "name": "Home-cooked / Mini banquet meal",
                                "description": "Simple home-cooked meal for 3 people.",
                                "estimated_price": 2000.0,
                                "quantity": 1,
                                "search_terms": "swiggy catering small party",
                                "shopping_links": {
                                    "swiggy": "https://www.swiggy.com/search?query=swiggy+catering+small+party",
                                    "zomato": "https://www.zomato.com/search?q=swiggy+catering+small+party"
                                }
                            }
                        ]
                    }
                ],
                "venue_suggestions": [
                    {
                        "name": "Home",
                        "type": "Residential",
                        "capacity": 10,
                        "estimated_cost": 0.0,
                        "search_links": {"google": "https://www.google.com/search?q=home+event+setup"}
                    }
                ],
                "additional_suggestions": ["Consider making meal a potluck style to reduce costs."]
            }
        ),
        RecommendationItem(
            id=str(uuid.uuid4())[:8],
            timestamp=(datetime.now(timezone.utc) - timedelta(days=1)).strftime("%b %d, %Y, %I:%M %p"),
            recommendation_type="jewelry",
            input_summary={
                "total_budget": 5000.0,
                "occasion": "Birthday",
                "has_image": True
            },
            result_summary="Jewelry Plan: Birthday celebration jewelry matched with uploaded outfit image within ₹5,000",
            full_result={
                "total_budget": 5000.0,
                "remaining_budget": 800.0,
                "outfit_analysis": {
                    "colors": ["Blue", "White"],
                    "style": "Casual",
                    "formality": "Informal"
                },
                "jewelry_recommendations": [
                    {
                        "item_type": "Bracelet",
                        "description": "Simple braided leather bracelet with metal accents.",
                        "style": "Casual",
                        "estimated_price": 500.0,
                        "shopping_links": {
                            "amazon": "https://www.amazon.in/s?k=braided+leather+bracelet",
                            "flipkart": "https://www.flipkart.com/search?q=braided+leather+bracelet"
                        }
                    }
                ],
                "styling_tips": ["Keep jewelry minimal to match casual outfit style."]
            }
        )
    ]

seed_default_user()


# ---------------------------------------------------------------------------
# AUTHENTICATION & SECURITY UTILITIES
# ---------------------------------------------------------------------------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "jti": str(uuid.uuid4())})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_token_from_request(request: Request) -> Optional[str]:
    """Retrieve token from either Authorization header or cookie."""
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        # Strip 'Bearer ' if stored inside cookie
        if cookie_token.startswith("Bearer "):
            return cookie_token.split(" ", 1)[1].strip()
        return cookie_token.strip()
    return None


async def get_current_user(request: Request) -> UserInDB:
    token = await get_token_from_request(request)
    if not token or token in blacklisted_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated or token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    user = users_db.get(username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    
    # Touch session last_activity
    if username in active_sessions:
        active_sessions[username].last_activity = datetime.now(timezone.utc)

    return user


async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_optional_current_user(request: Request) -> Optional[UserInDB]:
    """Optional auth for landing pages and navbars."""
    try:
        return await get_current_user(request)
    except Exception:
        return None


def save_upload_file(upload_file: UploadFile) -> str:
    """Save uploaded image file to static/uploads and return file path."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    clean_filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", upload_file.filename)
    saved_filename = f"{timestamp}_{clean_filename}"
    file_path = os.path.join("static", "uploads", saved_filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return file_path


def save_to_history(username: str, recommendation_type: str, input_data: dict, result: dict):
    """Save recommendation result to user history log."""
    if username not in user_recommendations:
        user_recommendations[username] = []
    
    now_str = datetime.now(timezone.utc).strftime("%b %d, %Y, %I:%M %p")
    rec_id = str(uuid.uuid4())[:8]

    # Format user friendly summary string
    if recommendation_type == "home":
        rooms = input_data.get("rooms") or "Living Room"
        summary_text = f"Home Budget Plan: ₹{input_data.get('total_budget', 0):,.2f} ({rooms})"
    elif recommendation_type == "party":
        summary_text = f"Party Budget Plan: ₹{input_data.get('total_budget', 0):,.2f} for {input_data.get('party_type', 'Event')}"
    elif recommendation_type == "jewelry":
        summary_text = f"Jewelry Budget Plan: ₹{input_data.get('total_budget', 0):,.2f} for {input_data.get('occasion', 'Occasion')}"
    else:
        summary_text = f"Budget Plan: ₹{input_data.get('total_budget', 0):,.2f}"

    item = RecommendationItem(
        id=rec_id,
        timestamp=now_str,
        recommendation_type=recommendation_type,
        input_summary=input_data,
        result_summary=summary_text,
        full_result=result
    )
    user_recommendations[username].insert(0, item)


# ---------------------------------------------------------------------------
# STARTUP & BACKGROUND TASKS (Activity 3.4)
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def setup_session_cleanup():
    """Background task to clean up expired sessions inactive for > 30 minutes."""
    async def cleanup_expired_sessions():
        while True:
            try:
                current_time = datetime.now(timezone.utc)
                expired_sessions = [
                    username for username, session in active_sessions.items()
                    if (current_time - session.last_activity).total_seconds() > 1800  # 30 minutes
                ]
                for username in expired_sessions:
                    if username in active_sessions:
                        del active_sessions[username]
            except Exception:
                pass
            await asyncio.sleep(300)  # Check every 5 minutes

    asyncio.create_task(cleanup_expired_sessions())


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# HTML WEB ROUTES (Jinja2 Templates)
# ---------------------------------------------------------------------------

def render_template(request: Request, name: str, context: Optional[Dict[str, Any]] = None) -> HTMLResponse:
    """Helper ensuring Starlette 1.7+ & older TemplateResponse compatibility."""
    ctx = context.copy() if context else {}
    ctx["request"] = request
    try:
        return templates.TemplateResponse(request=request, name=name, context=ctx)
    except TypeError:
        return templates.TemplateResponse(name, ctx)


@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    """Main landing page introducing PocketSmart AI features."""
    current_user = await get_optional_current_user(request)
    return render_template(request, "index.html", {"user": current_user})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the login page or redirect to dashboard if logged in."""
    current_user = await get_optional_current_user(request)
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return render_template(request, "login.html", {"user": None})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Serve the register page or redirect to dashboard if logged in."""
    current_user = await get_optional_current_user(request)
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return render_template(request, "register.html", {"user": None})


@app.get("/dashboard", response_class=HTMLResponse)
async def user_dashboard(request: Request):
    """Displays user dashboard with recent recommendations and quick planners."""
    current_user = await get_optional_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    history_items = user_recommendations.get(current_user.username, [])[:5]
    return render_template(
        request,
        "dashboard.html",
        {
            "user": current_user,
            "recent_recommendations": history_items
        }
    )


@app.get("/home-planner", response_class=HTMLResponse)
@app.get("/generate-home", response_class=HTMLResponse)
async def home_planner_page(request: Request):
    """Serve Home Interior Budget Planner page."""
    current_user = await get_optional_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return render_template(request, "home_planner.html", {"user": current_user})


@app.get("/party-planner", response_class=HTMLResponse)
@app.get("/generate-party", response_class=HTMLResponse)
async def party_planner_page(request: Request):
    """Serve Party Budget Planner page."""
    current_user = await get_optional_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return render_template(request, "party_planner.html", {"user": current_user})


@app.get("/jewelry-planner", response_class=HTMLResponse)
@app.get("/generate-jewelry", response_class=HTMLResponse)
async def jewelry_planner_page(request: Request):
    """Serve Jewelry Budget Planner page."""
    current_user = await get_optional_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return render_template(request, "jewelry_planner.html", {"user": current_user})


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """Serve History page to view past recommendations."""
    current_user = await get_optional_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    user_history = user_recommendations.get(current_user.username, [])
    return render_template(
        request,
        "history.html",
        {"user": current_user, "history": user_history}
    )


# ---------------------------------------------------------------------------
# AUTH & SESSION API ROUTES
# ---------------------------------------------------------------------------

@app.post("/register")
async def register(
    request: Request,
    username: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    full_name: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    confirm_password: Optional[str] = Form(None)
):
    """Handle new user registration from form or JSON."""
    # Support JSON payload if submitted as JSON
    if not username and request.headers.get("content-type", "").startswith("application/json"):
        try:
            body = await request.json()
            username = body.get("username")
            email = body.get("email")
            full_name = body.get("full_name")
            password = body.get("password")
            confirm_password = body.get("confirm_password", password)
        except Exception:
            pass

    if not username or not email or not password:
        raise HTTPException(status_code=400, detail="Username, email, and password are required")
    
    if confirm_password and password != confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    
    if username in users_db:
        raise HTTPException(status_code=400, detail="Username is already registered")

    hashed_pw = get_password_hash(password)
    new_user = UserInDB(
        username=username,
        email=email,
        full_name=full_name or username,
        hashed_password=hashed_pw
    )
    users_db[username] = new_user

    # Automatically log the user in
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(data={"sub": username}, expires_delta=access_token_expires)
    
    active_sessions[username] = UserSession(username=username, token=token)

    response = JSONResponse(
        content={"message": "Registration successful", "access_token": token, "token_type": "bearer", "username": username},
        status_code=status.HTTP_201_CREATED
    )
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    return response


@app.post("/token", response_model=Token)
async def login_for_access_token(
    response: JSONResponse,
    form_data: OAuth2PasswordRequestForm = Depends()
):
    """OAuth2 compatible token login (Activity 2.4, page 19)."""
    user = users_db.get(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # Manage active sessions
    existing_user_data = {}
    if user.username in active_sessions:
        existing_user_data = active_sessions[user.username].user_data
        old_token = active_sessions[user.username].token
        if old_token and old_token != access_token:
            blacklisted_tokens.add(old_token)

    active_sessions[user.username] = UserSession(
        username=user.username,
        token=access_token,
        user_data=existing_user_data
    )

    res = JSONResponse(content={"access_token": access_token, "token_type": "bearer"})
    res.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    return res


@app.post("/login")
async def login_endpoint(
    request: Request,
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None)
):
    """Standard login endpoint handling JSON and HTML Form submission."""
    if not username and request.headers.get("content-type", "").startswith("application/json"):
        try:
            body = await request.json()
            username = body.get("username")
            password = body.get("password")
        except Exception:
            pass

    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password are required")

    user = users_db.get(username)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    existing_user_data = {}
    if user.username in active_sessions:
        existing_user_data = active_sessions[user.username].user_data
        old_token = active_sessions[user.username].token
        if old_token and old_token != access_token:
            blacklisted_tokens.add(old_token)

    active_sessions[user.username] = UserSession(
        username=user.username,
        token=access_token,
        user_data=existing_user_data
    )

    res = JSONResponse(content={"message": "Login successful", "access_token": access_token, "token_type": "bearer"})
    res.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    return res


@app.post("/logout")
@app.get("/logout")
async def logout(request: Request):
    """Logout user by blacklisting their token and clearing session (Activity 2.3, page 19)."""
    token = await get_token_from_request(request)
    if token:
        blacklisted_tokens.add(token)
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            if username and username in active_sessions:
                del active_sessions[username]
        except JWTError:
            pass

    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    return response


@app.get("/session-info")
async def get_session_info(
    request: Request,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Retrieve metadata about the current user session (Activity 2.4, page 20)."""
    if current_user.username in active_sessions:
        session = active_sessions[current_user.username]
        duration_minutes = (datetime.now(timezone.utc) - session.login_time).total_seconds() // 60
        return {
            "username": session.username,
            "login_time": session.login_time.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "session_duration_minutes": int(duration_minutes),
            "user_data": session.user_data
        }
    raise HTTPException(status_code=404, detail="No active session found")


@app.post("/session-data")
async def update_session_data(
    data: Dict[str, Any],
    request: Request,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Update detailed session data for personalization (Activity 2.4, page 20)."""
    if current_user.username in active_sessions:
        active_sessions[current_user.username].user_data.update(data)
        active_sessions[current_user.username].last_activity = datetime.now(timezone.utc)
        return {"message": "Session data updated", "data": active_sessions[current_user.username].user_data}
    raise HTTPException(status_code=404, detail="No active session found")


# ---------------------------------------------------------------------------
# AI RECOMMENDATION ROUTES (Milestone 3)
# ---------------------------------------------------------------------------

@app.post("/home-budget")
@app.post("/generate-home")
async def plan_home_budget(
    request: Request,
    budget_input: Optional[HomeBudgetInput] = None,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Generate home interior recommendations (Activity 3.1, page 21)."""
    # Parse either JSON body or Form data
    if budget_input is None:
        try:
            form = await request.form()
            budget_input = HomeBudgetInput(
                total_budget=float(form.get("total_budget", 5000.0)),
                num_lights=int(form.get("num_lights", 0)),
                num_fans=int(form.get("num_fans", 0)),
                num_furniture=int(form.get("num_furniture", 0)),
                num_dining_tables=int(form.get("num_dining_tables", 0)),
                has_living_room=bool(form.get("has_living_room")),
                has_kitchen=bool(form.get("has_kitchen")),
                has_bedroom=bool(form.get("has_bedroom")),
                additional_requirements=form.get("additional_requirements")
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid home budget input parameters")

    # Store last budget planning in session data
    if current_user.username in active_sessions:
        active_sessions[current_user.username].user_data["last_home_budget"] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "budget": budget_input.total_budget,
            "requirements": {
                "lights": budget_input.num_lights,
                "fans": budget_input.num_fans,
                "furniture": budget_input.num_furniture,
                "dining_tables": budget_input.num_dining_tables
            }
        }

    # Get recommendations from Gemini utility
    result = get_home_recommendations(budget_input)

    # Save to history
    save_to_history(
        username=current_user.username,
        recommendation_type="home",
        input_data=budget_input.dict(),
        result=result
    )

    return result


@app.post("/party-budget")
@app.post("/generate-party")
async def plan_party_budget(
    request: Request,
    budget_input: Optional[PartyBudgetInput] = None,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Process party details and guest count to recommend venue, food, and decor (Activity 3.1, page 22)."""
    if budget_input is None:
        try:
            form = await request.form()
            budget_input = PartyBudgetInput(
                total_budget=float(form.get("total_budget", 5000.0)),
                party_type=str(form.get("party_type", "Birthday")),
                num_guests=int(form.get("num_guests", 10)),
                venue_type=str(form.get("venue_type", "Home")),
                needs_catering=bool(form.get("needs_catering")),
                needs_decoration=bool(form.get("needs_decoration")),
                needs_entertainment=bool(form.get("needs_entertainment")),
                additional_requirements=form.get("additional_requirements")
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid party budget input parameters")

    if current_user.username in active_sessions:
        active_sessions[current_user.username].user_data["last_party_budget"] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "budget": budget_input.total_budget,
            "party_type": budget_input.party_type,
            "guests": budget_input.num_guests
        }

    result = get_party_recommendations(budget_input)

    save_to_history(
        username=current_user.username,
        recommendation_type="party",
        input_data=budget_input.dict(),
        result=result
    )

    return result


@app.post("/jewelry-budget")
@app.post("/generate-jewelry")
async def plan_jewelry_budget(
    request: Request,
    total_budget: float = Form(...),
    occasion: str = Form(...),
    preferences: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Generate jewelry budget recommendations with optional outfit image (Activity 3.1, page 23)."""
    budget_input = JewelryBudgetInput(
        total_budget=total_budget,
        occasion=occasion,
        preferences=preferences
    )

    image_path = None
    image_filename = None
    if image and image.filename:
        image_path = save_upload_file(image)
        image_filename = image.filename

    if current_user.username in active_sessions:
        active_sessions[current_user.username].user_data["last_jewelry_budget"] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "budget": budget_input.total_budget,
            "occasion": budget_input.occasion,
            "has_image": image_path is not None
        }

    result = get_jewelry_recommendations(budget_input, image_path)

    # Save to history with image info
    input_data = budget_input.dict()
    if image_filename:
        input_data["image"] = image_filename
        input_data["image_url"] = f"/{image_path.replace(os.sep, '/')}"

    save_to_history(
        username=current_user.username,
        recommendation_type="jewelry",
        input_data=input_data,
        result=result
    )

    return result


# ---------------------------------------------------------------------------
# RECOMMENDATION HISTORY & DETAILS APIS (Activity 3.1 & 3.2, pages 23-24)
# ---------------------------------------------------------------------------

@app.get("/recommendation-history")
async def get_recommendation_history(
    request: Request,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Retrieve history of user queries and recommendations (page 23 & 24)."""
    if current_user.username not in user_recommendations:
        return {"history": []}

    history = user_recommendations[current_user.username]
    history_data = []
    for item in history:
        history_data.append({
            "id": item.id,
            "timestamp": item.timestamp,
            "type": item.recommendation_type,
            "input": item.input_summary,
            "summary": item.result_summary
        })
    return {"history": history_data}


@app.get("/recommendation-details/{recommendation_id}")
async def get_recommendation_details(
    recommendation_id: str,
    request: Request,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """Return full details of a specific past recommendation (Activity 3.2, page 24)."""
    if current_user.username not in user_recommendations:
        raise HTTPException(status_code=404, detail="No recommendations found")

    for item in user_recommendations[current_user.username]:
        if item.id == recommendation_id:
            return {
                "id": item.id,
                "timestamp": item.timestamp,
                "type": item.recommendation_type,
                "input": item.input_summary,
                "full_result": item.full_result
            }

    raise HTTPException(status_code=404, detail="Recommendation not found")


# ---------------------------------------------------------------------------
# MAIN RUNNER (Activity 3.4, page 25)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print("Starting PocketSmart: AI Budget Planner...")
    uvicorn.run("app:app", host=host, port=port, reload=True)
