from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.config import settings
from app.database import create_tables
from app.routers import claims, review


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once at startup — creates all tables
    create_tables()
    print(f"[startup] Tables ready. DB: {settings.database_url}")
    yield
    # Runs on shutdown (nothing to clean up for SQLite)
    print("[shutdown] Shutting down.")


app = FastAPI(
    title=settings.app_name,
    description=(
        "Operational claims intelligence agent. "
        "Deterministic pipeline + LLM reasoning + human-in-the-loop escalation."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(claims.router)
app.include_router(review.router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}

# Add this block to run the server when the script is executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",   # or "localhost"
        port=8000,
        reload=True,          # auto-reload on code changes (useful for development)
    )