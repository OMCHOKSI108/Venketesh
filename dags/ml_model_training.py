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
]

default_args = {
    "owner": "admin",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}

dag = DAG(
    "ml_model_training",
    default_args=default_args,
    schedule_interval="0 4 * * *",
    catchup=False,
    description="Daily ML Model Training Pipeline",
)

API_BASE = os.getenv("API_BASE", "http://app:8000")


def fetch_training_data(symbol, **context):
    """Ensure sufficient training data exists"""
    url = f"{API_BASE}/api/v1/ohlc/{symbol}/fetch"
    params = {"timeframe": "1d"}

    try:
        response = requests.post(url, params=params, timeout=60)
        if response.status_code == 200:
            print(f"✓ Fetched latest data for {symbol}")
            return {"symbol": symbol, "status": "success"}
        else:
            print(f"✗ Failed to fetch data for {symbol}")
            return {"symbol": symbol, "status": "failed"}
    except Exception as e:
        print(f"✗ Error fetching data for {symbol}: {str(e)}")
        return {"symbol": symbol, "status": "error", "error": str(e)}


def train_model_for_symbol(symbol, **context):
    """Train ML model for a single symbol"""
    url = f"{API_BASE}/api/v1/prediction/{symbol}/train"
    params = {"timeframe": "1d", "limit": 500}

    try:
        response = requests.post(url, params=params, timeout=120)
        if response.status_code == 200:
            result = response.json()
            accuracy = result.get("train_accuracy", 0)
            test_accuracy = result.get("test_accuracy", 0)
            samples = result.get("samples", 0)
            print(
                f"✓ Trained {symbol}: train_acc={accuracy}, test_acc={test_accuracy}, samples={samples}"
            )
            return {
                "symbol": symbol,
                "status": "success",
                "accuracy": accuracy,
                "test_accuracy": test_accuracy,
            }
        else:
            print(f"✗ Failed to train {symbol}: {response.status_code}")
            return {"symbol": symbol, "status": "failed", "error": response.status_code}
    except Exception as e:
        print(f"✗ Error training {symbol}: {str(e)}")
        return {"symbol": symbol, "status": "error", "error": str(e)}


def get_training_summary(**context):
    """Get summary of all trained models"""
    results = {"success": [], "failed": [], "total": len(SYMBOLS)}

    for symbol in SYMBOLS:
        url = f"{API_BASE}/api/v1/prediction/{symbol}/signals"
        params = {"timeframe": "1d", "limit": 100}

        try:
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if "error" not in data:
                    results["success"].append(symbol)
                    print(f"✓ {symbol} model ready")
                else:
                    results["failed"].append(symbol)
                    print(f"✗ {symbol} not ready: {data.get('error')}")
            else:
                results["failed"].append(symbol)
        except Exception as e:
            results["failed"].append(symbol)
            print(f"Error checking {symbol}: {e}")

    print(f"\n=== Training Summary ===")
    print(f"Success: {len(results['success'])}/{results['total']}")
    print(f"Ready: {results['success']}")
    print(f"Failed: {results['failed']}")

    return results


fetch_tasks = []
train_tasks = []

for symbol in SYMBOLS:
    fetch_op = PythonOperator(
        task_id=f"fetch_{symbol}",
        python_callable=fetch_training_data,
        op_args=[symbol],
        dag=dag,
    )
    train_op = PythonOperator(
        task_id=f"train_{symbol}",
        python_callable=train_model_for_symbol,
        op_args=[symbol],
        dag=dag,
    )

    fetch_op >> train_op
    fetch_tasks.append(fetch_op)
    train_tasks.append(train_op)

summary_op = PythonOperator(
    task_id="training_summary",
    python_callable=get_training_summary,
    dag=dag,
)

for t in train_tasks:
    summary_op.set_upstream(t)
