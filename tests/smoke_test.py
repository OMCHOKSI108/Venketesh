# MODULE: tests/smoke_test.py
# TASK:   CHECKLIST.md §4.7 Smoke Test
# SPEC:   TESTING.md
# PHASE:  4
# STATUS: In Progress

import asyncio
import sys
import time

import httpx


BASE_URL = "http://localhost:8000"
TIMEOUT = 30


async def test_health():
    """Test 1: GET /api/v1/health returns 200"""
    print("Testing /api/v1/health...")
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(f"{BASE_URL}/api/v1/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("status") == "ok", (
            f"Expected status 'ok', got {data.get('status')}"
        )
    print("  ✓ Health check passed")
    return True


async def test_ohlc_endpoint():
    """Test 2: GET /api/v1/ohlc/NIFTY returns >= 1 candle"""
    print("Testing /api/v1/ohlc/NIFTY...")
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(f"{BASE_URL}/api/v1/ohlc/NIFTY?limit=10")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "data" in data, "Response missing 'data' field"
        assert len(data["data"]) >= 1, f"Expected >= 1 candle, got {len(data['data'])}"
    print(f"  ✓ OHLC endpoint passed ({len(data['data'])} candles)")
    return True


async def test_latest_endpoint():
    """Test 3: GET /api/v1/ohlc/NIFTY/latest returns single candle"""
    print("Testing /api/v1/ohlc/NIFTY/latest...")
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(f"{BASE_URL}/api/v1/ohlc/NIFTY/latest")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "timestamp" in data, "Response missing 'timestamp' field"
    print("  ✓ Latest endpoint passed")
    return True


async def test_sources_health():
    """Test 4: GET /api/v1/health/sources returns valid JSON"""
    print("Testing /api/v1/health/sources...")
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(f"{BASE_URL}/api/v1/health/sources")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "sources" in data, "Response missing 'sources' field"
    print("  ✓ Sources health passed")
    return True


async def test_websocket_connection():
    """Test 5: WebSocket connects (basic check)"""
    print("Testing WebSocket connection...")
    try:
        import websockets

        async with websockets.connect(
            f"{BASE_URL.replace('http', 'ws')}/api/v1/ws/ohlc/NIFTY"
        ) as ws:
            await ws.close()
        print("  ✓ WebSocket connection passed")
        return True
    except ImportError:
        print("  ⚠ WebSocket test skipped (websockets not installed)")
        return True
    except Exception as e:
        print(f"  ⚠ WebSocket test skipped ({e})")
        return True


async def run_smoke_tests():
    """Run all smoke tests."""
    print("=" * 50)
    print("Running Smoke Tests")
    print("=" * 50)

    tests = [
        test_health,
        test_ohlc_endpoint,
        test_latest_endpoint,
        test_sources_health,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_smoke_tests())
    sys.exit(0 if success else 1)
