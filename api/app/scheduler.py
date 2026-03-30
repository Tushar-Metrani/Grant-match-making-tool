from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.scraper import fetch_grants_gov

scheduler = AsyncIOScheduler()

def start_scheduler():
    scheduler.add_job(
        fetch_grants_gov,
        trigger="interval",
        hours=24,
        id="grants_scraper",
        replace_existing=True
    )
    scheduler.start()
    print("Scheduler started — scraper runs every 24 hours")