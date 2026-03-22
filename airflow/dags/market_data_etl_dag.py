# airflow/dags/market_data_etl_dag.py
"""
Airflow DAG for Market Data ETL Pipeline

This DAG orchestrates the complete ETL workflow:
1. Fetch data from adapters (NSE/Yahoo)
2. Validate data
3. Store in PostgreSQL/TimescaleDB
4. Update Redis cache

Schedule: Every 2 minutes (to match POLL_INTERVAL)
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.redis.operators.redis import RedisOperator


# Default DAG arguments
default_args = {
    "owner": "market-data",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=1),
}


# DAG Definition
dag = DAG(
    "market_data_etl",
    default_args=default_args,
    description="Market Data ETL Pipeline - Fetch, Validate, Store",
    schedule_interval="*/2 * * * *",  # Every 2 minutes
    catchup=False,
    tags=["market-data", "etl", "ohlc"],
)


# Task 1: Run ETL Pipeline
def run_etl_pipeline(**context):
    """Execute the ETL pipeline."""
    import asyncio
    import sys

    sys.path.insert(0, "/app")

    from backend.services.etl import get_etl_pipeline

    async def run():
        pipeline = await get_etl_pipeline()
        result = await pipeline.run(symbol="NIFTY", timeframe="1m")
        return result

    return asyncio.run(run())


etl_task = PythonOperator(
    task_id="run_etl_pipeline",
    python_callable=run_etl_pipeline,
    dag=dag,
)


# Task 2: Verify Data in Redis
def verify_redis_cache(**context):
    """Verify latest data is in Redis cache."""
    import redis
    import json

    r = redis.Redis(host="redis", port=6379, db=0)
    data = r.get("ohlc:NIFTY:1m:current")

    if data:
        candles = json.loads(data)
        print(f"✓ Redis cache contains {len(candles)} candles")
        return True
    else:
        print("✗ Redis cache empty")
        return False


verify_cache = PythonOperator(
    task_id="verify_redis_cache",
    python_callable=verify_redis_cache,
    dag=dag,
)


# Task 3: Check PostgreSQL Data
def check_postgres_data(**context):
    """Check if data was written to PostgreSQL."""
    import asyncpg
    import asyncio

    async def check():
        conn = await asyncpg.connect(
            host="postgres",
            port=5432,
            user="market",
            password="market",
            database="marketdata",
        )

        result = await conn.fetchval(
            "SELECT COUNT(*) FROM ohlc_data WHERE symbol = 'NIFTY'"
        )

        await conn.close()
        print(f"✓ PostgreSQL contains {result} NIFTY records")
        return result

    return asyncio.run(check())


check_db = PythonOperator(
    task_id="check_postgres_data",
    python_callable=check_postgres_data,
    dag=dag,
)


# Task 4: Update Source Health
def update_source_health(**context):
    """Update source health status."""
    import requests

    # This calls the health endpoint to update source status
    try:
        response = requests.get("http://backend:8000/api/v1/health/sources")
        if response.status_code == 200:
            print("✓ Source health updated")
            return True
    except Exception as e:
        print(f"✗ Source health update failed: {e}")
        return False


health_update = PythonOperator(
    task_id="update_source_health",
    python_callable=update_source_health,
    dag=dag,
)


# Task Dependencies
etl_task >> verify_cache >> check_db >> health_update


# Additional: SQL-based validation task
validate_schema = PostgresOperator(
    task_id="validate_schema",
    postgres_conn_id="postgres_default",
    sql="""
        SELECT COUNT(*) > 0 FROM information_schema.tables 
        WHERE table_name = 'ohlc_data';
    """,
    dag=dag,
)


# Run schema validation first
validate_schema >> etl_task
