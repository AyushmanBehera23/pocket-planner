"""
Pocket Planner — FastAPI Backend Entry Point
Run with: uvicorn main:app --reload --port 8000
"""

import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from services.database import db_service
from routers import extract, expenses
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: seed DB. Shutdown: close connections."""
    await db_service.initialize()
    yield
    await db_service.close()


app = FastAPI(
    title="Pocket Planner API",
    description="AI-powered bill extraction and expense tracking using Gemini Vision",
    version="2.0.0",
    lifespan=lifespan,
)

# B-05: allow any localhost port so Vite port conflicts don't break CORS
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(extract.router, prefix="/api", tags=["extraction"])
app.include_router(expenses.router, prefix="/api", tags=["expenses"])


@app.get("/health", tags=["system"])
async def health_check():
    """B-07: used by frontend to determine ONLINE/OFFLINE status."""
    count = await db_service.count()
    return {
        "status": "healthy",
        "service": "pocket-planner-api",
        "version": "2.0.0",
        "expenses_stored": count,
    }
