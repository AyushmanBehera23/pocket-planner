# 💳 Pocket Planner — AI-Powered Expense Tracker

A full-stack web application that uses **Google Gemini Vision** to extract structured data from bill photos and PDFs, then tracks your spending with a slick cloud dashboard.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Vite + Tailwind CSS |
| Backend | Python FastAPI (async) |
| AI | Google Gemini 1.5 Flash (multimodal) |
| Database | Mock MongoDB-style (in-memory, swap for Motor) |

## Project Structure

```
pocket-planner/
├── backend/
│   ├── main.py                # FastAPI app entry point
│   ├── requirements.txt       # Python dependencies
│   ├── .env.example           # Environment variable template
│   ├── core/
│   │   └── config.py          # App configuration
│   ├── models/
│   │   └── schemas.py         # Pydantic data models + validators
│   ├── services/
│   │   ├── gemini.py          # Gemini Vision API client + mock
│   │   └── database.py        # Async MongoDB-style data layer
│   └── routers/
│       ├── extract.py         # POST /api/extract
│       └── expenses.py        # GET/DELETE /api/expenses
│
└── frontend/
    ├── index.html
    ├── vite.config.js         # Vite + proxy config
    ├── package.json
    └── src/
        ├── main.jsx           # React entry point
        └── App.jsx            # Full application (modular components)
```

## Quick Start

### 1. Backend

```bash
cd pocket-planner/backend

# Install dependencies
pip install -r requirements.txt

# Configure (optional — runs in demo mode without API key)
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Start the API server
uvicorn main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### 2. Frontend

```bash
cd pocket-planner/frontend

npm install
npm run dev
# Opens at http://localhost:5173
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/extract` | Upload bill → Gemini extraction → saved record |
| `GET` | `/api/expenses` | List all expenses with monthly total |
| `GET` | `/api/expenses/summary` | Category + monthly spending breakdown |
| `DELETE` | `/api/expenses/{id}` | Remove an expense record |
| `GET` | `/health` | Service health check |

## Demo Mode

Run without a Gemini API key — the `MockGeminiService` rotates through 4 realistic bills with a simulated 1.8s processing delay. The UI also falls back to rich mock data if the backend is unreachable.

## Production Upgrade Path

- **Database**: Replace `MockCollection` with [Motor](https://motor.readthedocs.io/) (async MongoDB)
- **Auth**: Add JWT middleware to FastAPI routes
- **Storage**: Upload files to S3/GCS instead of processing in-memory
- **Deployment**: Dockerfile included — deploy backend to Cloud Run, frontend to Vercel
