from fastapi import APIRouter, Query
from app.etl.runner import run_etl_with_logs
from app.core.constants import SUPPORTED_SYMBOLS
import logging

router = APIRouter(prefix="/etl", tags=["ETL"])
logger = logging.getLogger(__name__)


@router.post("/run")
async def run_etl(
    category: str = Query("all", pattern="^(all|indian|us|world)$"),
    symbols: str = Query(None, description="Comma-separated symbols (optional)"),
):
    """
    Run ETL pipeline and return logs
    - category: all, indian, us, world
    - symbols: Optional comma-separated list (overrides category)
    """
    logger.info(f"Starting ETL for category={category}, symbols={symbols}")

    symbol_list = None
    if symbols:
        symbol_list = [s.strip() for s in symbols.split(",")]

    result = await run_etl_with_logs(category)

    return {
        "status": "completed",
        "category": category,
        "results": result["results"],
        "logs": result["logs"],
        "total_logs": len(result["logs"]),
    }


@router.get("/logs")
async def get_etl_logs():
    """Get recent ETL logs (placeholder - returns last run info)"""
    return {
        "message": "ETL logs are returned in /etl/run response",
        "endpoints": {
            "POST /etl/run": "Run ETL pipeline with logs",
            "GET /etl/logs": "This endpoint",
        },
    }


@router.get("/symbols")
async def get_supported_symbols():
    """Get supported symbols by category"""
    return {
        "indian": ["NIFTY", "BANKNIFTY", "SENSEX", "NIFTYIT"],
        "us": ["DOWJONES", "NASDAQ", "SP500"],
        "world": ["FTSE", "DAX", "NIKKEI"],
        "all": [
            "NIFTY",
            "BANKNIFTY",
            "SENSEX",
            "NIFTYIT",
            "DOWJONES",
            "NASDAQ",
            "SP500",
            "FTSE",
            "DAX",
            "NIKKEI",
        ],
    }
