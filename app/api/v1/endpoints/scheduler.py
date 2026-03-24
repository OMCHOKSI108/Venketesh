from fastapi import APIRouter
from app.etl.scheduler import scheduler

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


@router.get("/status")
async def get_scheduler_status():
    return scheduler.get_status()


@router.post("/run")
async def run_scheduler_now():
    if not scheduler._running:
        return {"error": "Scheduler not running"}
    result = await scheduler._run_job()
    return {"status": "completed", "result": result}


@router.post("/start")
async def start_scheduler(interval_seconds: int = 300):
    if scheduler._running:
        return {"error": "Scheduler already running"}
    await scheduler.start(interval_seconds)
    return {"status": "started", "interval": interval_seconds}


@router.post("/stop")
async def stop_scheduler():
    if not scheduler._running:
        return {"error": "Scheduler not running"}
    await scheduler.stop()
    return {"status": "stopped"}
