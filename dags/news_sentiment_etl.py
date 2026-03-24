from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
import requests
import os

NEWS_SYMBOLS = [
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
    "retry_delay": timedelta(minutes=5),
}

dag = DAG(
    "news_sentiment_etl",
    default_args=default_args,
    schedule_interval="*/10 * * * *",
    catchup=False,
    description="News Extraction and Sentiment Analysis Pipeline - Parallel",
)

API_BASE = os.getenv("API_BASE", "http://app:8000")


def fetch_news(**context):
    """Fetch news from all sources"""
    url = f"{API_BASE}/api/v1/news/fetch"
    try:
        response = requests.post(url, timeout=180)
        if response.status_code == 200:
            result = response.json()
            articles = result.get("articles_added", 0)
            print(f"✓ News fetched: {articles} articles")
            return {"status": "success", "articles_added": articles}
        else:
            print(f"✗ News fetch failed: HTTP {response.status_code}")
            return {"status": "failed", "error": f"HTTP {response.status_code}"}
    except Exception as e:
        print(f"✗ News fetch error: {e}")
        return {"status": "failed", "error": str(e)}


def process_sentiment(**context):
    """Trigger sentiment computation via API"""
    url = f"{API_BASE}/api/v1/news/sentiment"
    try:
        response = requests.get(url, timeout=60)
        if response.status_code == 200:
            result = response.json()
            count = len(result.get("data", []))
            print(f"✓ Sentiment computed: {count} symbols processed")
            return {"status": "success", "symbols_processed": count}
        else:
            print(f"✗ Sentiment compute failed: HTTP {response.status_code}")
            return {"status": "failed", "error": f"HTTP {response.status_code}"}
    except Exception as e:
        print(f"✗ Sentiment compute error: {e}")
        return {"status": "failed", "error": str(e)}


def get_symbol_sentiment(symbol, **context):
    """Get sentiment for a specific symbol in parallel"""
    url = f"{API_BASE}/api/v1/news/sentiment/{symbol}"
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            label = data.get("sentiment_label", "NEUTRAL")
            score = data.get("sentiment_score", 0)
            print(f"✓ {symbol}: {label} ({score:+.2f})")
            return {"symbol": symbol, "label": label, "score": score, "status": "success"}
        else:
            print(f"✗ {symbol}: HTTP {response.status_code}")
            return {"symbol": symbol, "status": "failed"}
    except Exception as e:
        print(f"✗ {symbol}: {e}")
        return {"symbol": symbol, "status": "error", "error": str(e)}


def aggregate_all_sentiments(**context):
    """Aggregate all symbol sentiments"""
    print("\n" + "=" * 60)
    print("📊 SENTIMENT AGGREGATION RESULTS")
    print("=" * 60)

    sentiments = {}
    for symbol in NEWS_SYMBOLS:
        result = get_symbol_sentiment(symbol)
        if result.get("status") == "success":
            sentiments[symbol] = result

    bullish = [s for s, d in sentiments.items() if d.get("label") == "BULLISH"]
    bearish = [s for s, d in sentiments.items() if d.get("label") == "BEARISH"]
    neutral = [s for s, d in sentiments.items() if d.get("label") == "NEUTRAL"]

    print(f"\n📈 BULLISH ({len(bullish)}): {', '.join(bullish) if bullish else 'None'}")
    print(f"📉 BEARISH ({len(bearish)}): {', '.join(bearish) if bearish else 'None'}")
    print(f"📊 NEUTRAL ({len(neutral)}): {', '.join(neutral) if neutral else 'None'}")
    print("=" * 60 + "\n")

    return {"bullish": bullish, "bearish": bearish, "neutral": neutral}


def generate_trading_signals(**context):
    """Generate trading signals based on sentiment"""
    print("\n" + "=" * 60)
    print("📋 TRADING SIGNALS")
    print("=" * 60)

    signals = []
    for symbol in NEWS_SYMBOLS:
        result = get_symbol_sentiment(symbol)
        if result.get("status") == "success":
            label = result.get("label", "NEUTRAL")
            score = result.get("score", 0)

            if label == "BULLISH" and score > 0.3:
                signal = "BUY"
                action = "Consider LONG positions"
            elif label == "BEARISH" and score < -0.3:
                signal = "SELL"
                action = "Consider SHORT positions"
            else:
                signal = "HOLD"
                action = "Wait for clearer signals"

            emoji = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "🟡"
            print(f"  {emoji} {symbol:10} | {signal:4} | {action}")
            signals.append({"symbol": symbol, "signal": signal, "score": score})

    print("=" * 60 + "\n")
    return signals


# Task Definitions
fetch_news_task = PythonOperator(
    task_id="fetch_news",
    python_callable=fetch_news,
    dag=dag,
)

process_sentiment_task = PythonOperator(
    task_id="process_sentiment",
    python_callable=process_sentiment,
    dag=dag,
)

aggregate_task = PythonOperator(
    task_id="aggregate_sentiments",
    python_callable=aggregate_all_sentiments,
    dag=dag,
)

signals_task = PythonOperator(
    task_id="generate_signals",
    python_callable=generate_trading_signals,
    dag=dag,
)

# Parallel sentiment tasks for each symbol
sentiment_tasks = []
for symbol in NEWS_SYMBOLS:
    task = PythonOperator(
        task_id=f"get_sentiment_{symbol}",
        python_callable=get_symbol_sentiment,
        op_args=[symbol],
        dag=dag,
    )
    sentiment_tasks.append(task)

# DAG Dependencies - Parallel processing
fetch_news_task >> process_sentiment_task

# All sentiment tasks run in parallel after sentiment processing
for task in sentiment_tasks:
    process_sentiment_task >> task

# Aggregate and generate signals after all sentiments collected
aggregate_task.set_upstream(sentiment_tasks)
signals_task.set_upstream(aggregate_task)
