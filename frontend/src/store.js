/**
 * Central Store
 * Manages application state for market data
 */

const createStore = () => {
    const state = {
        symbol: 'NIFTY',
        timeframe: '1m',
        historicalData: [],
        realtimeCandle: null,
        wsConnected: false,
        wsStatus: 'disconnected',
        dataSource: 'unknown',
        lastUpdate: null,
    };

    const listeners = [];

    const subscribe = (listener) => {
        listeners.push(listener);
        return () => {
            const index = listeners.indexOf(listener);
            if (index > -1) {
                listeners.splice(index, 1);
            }
        };
    };

    const notify = () => {
        listeners.forEach(listener => listener(state));
    };

    const setSymbol = (symbol) => {
        state.symbol = symbol.toUpperCase();
        state.historicalData = [];
        state.realtimeCandle = null;
        notify();
    };

    const setTimeframe = (timeframe) => {
        state.timeframe = timeframe;
        state.historicalData = [];
        state.realtimeCandle = null;
        notify();
    };

    const setHistoricalData = (data) => {
        state.historicalData = data;
        notify();
    };

    const updateRealtimeCandle = (candle) => {
        if (!candle) return;
        
        const ts = candle.timestamp;
        const existing = state.historicalData.find(
            c => new Date(c.timestamp).getTime() === new Date(ts).getTime()
        );
        
        if (existing) {
            Object.assign(existing, candle);
        } else {
            state.historicalData.push(candle);
            state.historicalData.sort(
                (a, b) => new Date(a.timestamp) - new Date(b.timestamp)
            );
        }
        
        state.realtimeCandle = candle;
        state.lastUpdate = new Date().toISOString();
        notify();
    };

    const setWsStatus = (status) => {
        state.wsStatus = status;
        state.wsConnected = status === 'connected';
        notify();
    };

    const setDataSource = (source) => {
        state.dataSource = source;
        notify();
    };

    const getState = () => ({ ...state });

    return {
        subscribe,
        setSymbol,
        setTimeframe,
        setHistoricalData,
        updateRealtimeCandle,
        setWsStatus,
        setDataSource,
        getState,
    };
};

const store = createStore();

export default store;