from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import requests
import os

SYMBOLS = [
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
]

default_args = {
    "owner": "admin",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "market_data_etl",
    default_args=default_args,
    schedule_interval="*/15 * * * *",
    catchup=False,
    description="Fetch market data from Yahoo Finance and store in database",
)

API_BASE = os.getenv("API_BASE", "http://localhost:8000")


def fetch_market_data(symbol, **context):
    """Fetch data from Yahoo Finance via API"""
    url = f"{API_BASE}/api/v1/ohlc/{symbol}/fetch"
    params = {"timeframe": "1d"}
    response = requests.post(url, params=params)
    return response.json()


def extract_all_symbols(**context):
    """Extract data for all symbols"""
    results = []
    for symbol in SYMBOLS:
        try:
            result = fetch_market_data(symbol)
            results.append({"symbol": symbol, "success": result.get("success", False)})
            print(f"Fetched {symbol}: {result.get('success', False)}")
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            results.append({"symbol": symbol, "success": False, "error": str(e)})
    return results


def transform_data(**context):
    """Transform the data - could add calculations here"""
    ti = context["task_instance"]
    results = ti.xcom_pull(task_ids="extract_data")
    transformed = []
    for r in results:
        if r.get("success"):
            transformed.append(f"Processed {r['symbol']}")
    return transformed


def load_to_database(**context):
    """Data is already loaded via API - this is a checkpoint"""
    print("Data loaded to database successfully!")
    return True


extract_task = PythonOperator(
    task_id="extract_data",
    python_callable=extract_all_symbols,
    dag=dag,
)

transform_task = PythonOperator(
    task_id="transform_data",
    python_callable=transform_data,
    dag=dag,
)

load_task = PythonOperator(
    task_id="load_data",
    python_callable=load_to_database,
    dag=dag,
)

extract_task >> transform_task >> load_task
