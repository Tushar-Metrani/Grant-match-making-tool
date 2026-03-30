from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.scheduler import start_scheduler
from app.scraper import fetch_grants_gov
from app.routes.match import router
from app.database import supabase
import asyncio

async def run_scrape_if_empty():
    await asyncio.sleep(5)  # wait for app to fully start
    try:
        existing = supabase.table("grants").select("id").limit(1).execute()
        if not existing.data:
            print("DB is empty — running initial scrape...")
            await fetch_grants_gov()
        else:
            print("DB already has data — skipping initial scrape")
    except Exception as e:
        print(f"Scrape error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(run_scrape_if_empty())
    start_scheduler()
    yield
    print("Shutting down...")

app = FastAPI(
    title="GrantScope API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(router)

@app.get("/")
async def root():
    return {"status": "ok", "message": "GrantScope API is running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}