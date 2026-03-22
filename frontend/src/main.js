/**
 * Main Application Entry Point
 * Wires together WebSocket, store, and chart components
 */

import WebSocketManager from './services/websocket.js';
import store from './store.js';
import Chart from './components/Chart.js';
import StatusIndicator from './components/StatusIndicator.js';

const API_BASE = window.location.origin + '/api/v1';
let chart, wsManager, statusIndicator;

async function initApp() {
    const state = store.getState();
    
    chart = new Chart('chart');
    chart.init();
    
    statusIndicator = new StatusIndicator('status-container');
    statusIndicator.init();
    
    await loadHistoricalData(state.symbol, state.timeframe);
    
    wsManager = new WebSocketManager();
    wsManager.onCandle = handleCandle;
    wsManager.onHeartbeat = handleHeartbeat;
    wsManager.onStatusChange = handleStatusChange;
    wsManager.onError = handleError;
    
    wsManager.connect(state.symbol, state.timeframe);
    
    store.subscribe(handleStoreChange);
    
    document.getElementById('symbol-selector')?.addEventListener('change', (e) => {
        const newSymbol = e.target.value;
        changeSymbol(newSymbol);
    });
}

async function loadHistoricalData(symbol, timeframe) {
    try {
        updateStatus('loading');
        
        const response = await fetch(
            `${API_BASE}/ohlc/${symbol}?timeframe=${timeframe}&limit=200`
        );
        
        if (!response.ok) {
            throw new Error('Failed to fetch data');
        }
        
        const data = await response.json();
        
        if (data.data && data.data.length > 0) {
            store.setHistoricalData(data.data);
            store.setDataSource(data.meta?.source || 'unknown');
            chart.loadHistory(data.data);
            
            if (data.data.length > 0) {
                store.updateRealtimeCandle(data.data[data.data.length - 1]);
            }
        }
        
        updateStatus('connected');
    } catch (error) {
        console.error('Failed to load historical data:', error);
        updateStatus('offline');
    }
}

function handleCandle(candle) {
    if (!candle) return;
    
    candle = candle.data || candle;
    store.updateRealtimeCandle(candle);
    
    const isUpdate = store.getState().historicalData.some(
        c => new Date(c.timestamp).getTime() === new Date(candle.timestamp).getTime()
    );
    
    if (isUpdate) {
        chart.updateCandle(candle);
    } else {
        chart.appendCandle(candle);
    }
}

function handleHeartbeat(message) {
    console.log('Heartbeat:', message);
}

function handleStatusChange(status) {
    store.setWsStatus(status);
}

function handleError(error) {
    console.error('WebSocket error:', error);
}

function handleStoreChange(state) {
    if (statusIndicator) {
        statusIndicator.update(state);
    }
    
    const symbolLabel = document.getElementById('symbol-label');
    if (symbolLabel) {
        symbolLabel.textContent = state.symbol;
    }
    
    const sourceLabel = document.getElementById('source-indicator');
    if (sourceLabel) {
        sourceLabel.textContent = state.dataSource || state.wsStatus;
    }
}

async function changeSymbol(newSymbol) {
    if (wsManager) {
        wsManager.disconnect();
    }
    
    store.setSymbol(newSymbol);
    
    document.getElementById('symbol-label').textContent = newSymbol;
    
    await loadHistoricalData(newSymbol, store.getState().timeframe);
    
    wsManager.connect(newSymbol, store.getState().timeframe);
}

function updateStatus(status) {
    const dot = document.getElementById('status-dot');
    const label = document.getElementById('source-indicator');
    
    if (dot) {
        dot.classList.remove('bg-green-500', 'bg-yellow-500', 'bg-red-500');
        
        switch (status) {
            case 'connected':
                dot.classList.add('bg-green-500');
                if (label) label.textContent = 'Live';
                break;
            case 'loading':
                dot.classList.add('bg-yellow-500');
                if (label) label.textContent = 'Loading...';
                break;
            default:
                dot.classList.add('bg-red-500');
                if (label) label.textContent = 'Offline';
        }
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}