"""
Pocket Planner — FastAPI Backend Entry Point
Run with: uvicorn main:app --reload --port 8000
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from services.database import db_service
from routers import extract, expenses

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
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(extract.router, prefix="/api", tags=["extraction"])
app.include_router(expenses.router, prefix="/api", tags=["expenses"])


@app.get("/health", tags=["system"])
async def health_check():
    count = await db_service.expenses.count()
    return {
        "status": "healthy",
        "service": "pocket-planner-api",
        "expenses_stored": count,
    }
