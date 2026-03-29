import httpx
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.scraper import fetch_grants_gov

scheduler = AsyncIOScheduler()

async def keep_alive(app_url: str):
    try:
        async with httpx.AsyncClient() as client:
            await client.get(f"{app_url}/health", timeout=10)
            print("Keep-alive ping sent")
    except Exception as e:
        print(f"Keep-alive failed: {e}")

def start_scheduler(app_url: str = None):
    scheduler.add_job(
        fetch_grants_gov,
        trigger="interval",
        hours=24,
        id="grants_scraper",
        replace_existing=True
    )
    if app_url:
        scheduler.add_job(
            keep_alive,
            args=[app_url],
            trigger="interval",
            minutes=10,
            id="keep_alive",
            replace_existing=True
        )
    scheduler.start()
    print("Scheduler started — scraper runs every 24 hours")