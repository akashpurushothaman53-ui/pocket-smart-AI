# PocketSmart AI: Your Smart Budget & Recommendation Assistant

**PocketSmart AI** is a GenAI-powered, cross-platform budget allocation and recommendation assistant. It helps users plan home interiors, organize parties, and select occasion jewelry within defined budgets by synthesizing preferences, constraints, and multimodal inputs (text and images).

The platform leverages **FastAPI** for an asynchronous backend, **Google Gemini 1.5 Flash / 2.0** for intelligent reasoning and vision processing, and a responsive **Jinja2 + HTML5/CSS3/JavaScript** frontend with integrated cross-platform shopping links (Amazon, Flipkart, IKEA, Swiggy, Zomato, BookMyShow, BlueStone, Tanishq, CaratLane, and more).

---

## 🚀 Key Features & Scenarios

### 1. Home Interior Budget Planner
- Allocates budgets dynamically across lighting, ceiling fans, core furniture pieces, and dining tables.
- Supports multi-room scope (Living Room, Kitchen, Bedroom).
- Outputs itemized product suggestions, costs, quantity allocations, calculation tables (% of budget), remaining funds, and direct shopping links (Amazon India, Flipkart, IKEA, Myntra, Ajio).

### 2. AI-Based Party Budget Planner
- Analyzes event type (Wedding, Birthday, Corporate, House Party, etc.), venue type, and guest count.
- Proportionally allocates budgets across catering, decoration, entertainment, venue fees, and emergency contingencies.
- Delivers tailored vendor suggestions across Swiggy, Zomato, BigBasket, BookMyShow, MakeMyTrip, OYO rooms, and NoBroker.

### 3. Jewelry Recommendations for Occasions (Multimodal AI)
- Accepts occasion (Wedding, Birthday, Festival, Daily Wear) and style preferences.
- **Multimodal Outfit Vision:** Upload an outfit image to let Gemini AI analyze color palettes, design aesthetics, and formality levels.
- Generates curated accessory suggestions (necklaces, earrings, bracelets, rings, watches) with direct purchase links (BlueStone, Tanishq, CaratLane, Melorra, Meesho, Amazon, Flipkart).

### 4. Authentication, Session & History Management
- Secure user registration and login with JWT (JSON Web Tokens) and bcrypt password hashing.
- Dual-mode authentication (HTTP-Only Cookie for web UI + Bearer Header for REST APIs).
- Session tracking with metadata (`/session-info`) and automatic background cleanup for inactive sessions.
- Full recommendation history log with quick search and an interactive **"View Full Details"** modal.
- Built-in fallback recommendation engine providing realistic Indian market budget estimates if the Gemini API key is not configured or offline.

---

## 📁 Project Directory Structure

```text
PROJECT POCKET_SMART_AI/
├── static/
│   ├── uploads/            # Uploaded outfit images for multimodal AI
│   └── styles.css          # Design system & responsive styles matching UI specs
├── templates/
│   ├── index.html          # Landing page (Hero, Planner cards, Testimonials, CTA, Footer)
│   ├── login.html          # User authentication login card
│   ├── register.html       # User account creation form
│   ├── dashboard.html      # User dashboard, recent activity, and quick shortcuts
│   ├── home_planner.html   # Home Interior Planner form & live AI recommendation display
│   ├── party_planner.html  # Party Planner form & event budget breakdown
│   ├── jewelry_planner.html# Jewelry Planner with image drag-and-drop & outfit analysis
│   └── history.html        # Saved recommendation history & details modal
├── .env                    # Environment variables (API keys, JWT secret, ports)
├── .env.example            # Sample environment configuration template
├── requirements.txt        # Python package dependencies
├── gemini_utils.py         # AI orchestration, prompts, multimodal analysis & fallback logic
├── app.py                  # Core FastAPI application, security, routing, and APIs
├── main.py                 # Application launcher entry point
├── test_app.py             # Automated end-to-end test suite (100% test coverage)
└── README.md               # Setup and usage guide
```

---

## 🛠️ VS Code Setup & Installation

### Step 1: Open the Project in VS Code
1. Launch **Visual Studio Code**.
2. Go to **File** > **Open Folder...** and select:
   ```text
   PROJECT POCKET_SMART_AI
   ```
3. Recommended VS Code Extensions:
   - **Python** (by Microsoft)
   - **Pylance** (by Microsoft)
   - **Jinja** or **Better Jinja** (for `.html` syntax highlighting)

---

### Step 2: Set Up Python Environment

Open the VS Code integrated terminal (`Ctrl + ~` or **Terminal** > **New Terminal**):

#### Windows (PowerShell or Command Prompt):
```powershell
# Create a virtual environment (optional but recommended)
py -m venv venv

# Activate the virtual environment
.\venv\Scripts\Activate.ps1
# (Or in Command Prompt: .\venv\Scripts\activate.bat)
```

#### macOS / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

---

### Step 3: Install Required Dependencies

Run the following command in the terminal:
```bash
pip install -r requirements.txt
```

---

### Step 4: Configure Your Gemini API Key

1. Obtain a free Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Open the `.env` file in the project root:
   ```ini
   # Google Gemini API Key
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   GOOGLE_API_KEY=your_actual_gemini_api_key_here

   # JWT Authentication Secret
   SECRET_KEY=pocketsmart_ai_super_secret_jwt_key_2025_secure_token
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=1440

   # Server Configuration
   HOST=0.0.0.0
   PORT=8000
   ```
> **Note:** If no API key is provided, the application runs in **Intelligent Fallback Mode** so you can immediately test all UI flows, calculations, and shopping links without any errors.

---

## 💻 Running the Application

Start the development server with auto-reload:

```bash
# Option A: Run via main.py
python main.py

# Option B: Run via Uvicorn CLI
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Once started, open your web browser and navigate to:
```text
http://localhost:8000
```

---

## 🧪 Testing the Application

### 1. Automated Test Suite
A complete test suite is included in `test_app.py`. To run all automated tests:

```bash
python test_app.py
```

Expected output:
```text
Starting PocketSmart AI Test Suite...

--- Testing Public HTML Pages ---
✓ Landing page (/) loaded successfully
✓ Login page (/login) loaded successfully
✓ Register page (/register) loaded successfully

--- Testing Authentication & Sessions ---
✓ Login verified for 'sai'. Received token.
✓ Dashboard accessible with authenticated token
✓ Session info endpoint (/session-info) verified

--- Testing Home Interior Budget Planner ---
✓ Home Budget Recommendations returned valid categories, items & shopping links

--- Testing Party Budget Planner ---
✓ Party Budget Recommendations returned valid categories, guest allocations & vendor links

--- Testing Jewelry Budget Planner ---
✓ Jewelry Budget Recommendations returned valid styling analysis & jewelry catalog links

--- Testing History & Details API ---
✓ Recommendation history retrieved (6 items)
✓ Recommendation details for ID verified

==========================================
  ALL TESTS PASSED SUCCESSFULLY! (100%)   
==========================================
```

---

### 2. Manual Walkthrough & Demo Credentials

1. **Pre-configured Demo Account:**
   - **Username:** `sai`
   - **Password:** `password123`
   *(Or click "Create Account" on `/register` to create your own account)*

2. **Step-by-Step UI Verification:**
   - **Landing Page (`/`):** View the Hero section, explore planner cards, read user testimonials, and check the footer.
   - **Sign In (`/login`):** Log in using `sai` / `password123`.
   - **Dashboard (`/dashboard`):** Check your greeting, recent activities, and planner launcher cards.
   - **Home Interior Planner (`/home-planner`):**
     - Enter budget (e.g. `5000`), specify lights, fans, furniture pieces, and dining tables.
     - Click **"Generate Recommendations"**.
     - View the personalized budget breakdown, calculation table, and click shopping links for Amazon, Flipkart, IKEA, Myntra, and Ajio.
   - **Party Planner (`/party-planner`):**
     - Select event type (e.g. Birthday), guest count (e.g. `15`), venue type (e.g. Banquet Hall), and party needs (Catering, Decoration, Entertainment).
     - Click **"Generate Budget Plan"**.
     - View allocated expenditures and vendor links for Swiggy, Zomato, BookMyShow, MakeMyTrip, and OYO.
   - **Jewelry Planner (`/jewelry-planner`):**
     - Input budget and occasion (e.g. Wedding).
     - *(Optional)* Drag & drop or select an outfit image.
     - Click **"Get Recommendations"**.
     - View outfit color/style analysis, accessory recommendations, and store links for BlueStone, Tanishq, CaratLane, and Melorra.
   - **History (`/history`):**
     - View your saved past queries.
     - Click **"View Full Details"** on any card to open the interactive modal breakdown.

---

## 📚 Interactive API Documentation

FastAPI provides interactive API docs out of the box:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
