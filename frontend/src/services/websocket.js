/**
 * WebSocket Manager Service
 * Handles WebSocket connections with exponential backoff reconnection
 */

class WebSocketManager {
    constructor() {
        this.ws = null;
        this.symbol = null;
        this.timeframe = '1m';
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.baseDelay = 1000;
        this.maxDelay = 30000;
        
        this.onCandle = null;
        this.onHeartbeat = null;
        this.onStatusChange = null;
        this.onError = null;
    }

    connect(symbol, timeframe = '1m') {
        this.symbol = symbol.toUpperCase();
        this.timeframe = timeframe;
        this._establishConnection();
    }

    _establishConnection() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const url = `${protocol}//${host}/api/v1/ws/ohlc/${this.symbol}?timeframe=${this.timeframe}`;
        
        try {
            this.ws = new WebSocket(url);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
                if (this.onStatusChange) {
                    this.onStatusChange('connected');
                }
            };
            
            this.ws.onmessage = (event) => {
                this._handleMessage(event);
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                if (this.onError) {
                    this.onError(error);
                }
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket closed');
                if (this.onStatusChange) {
                    this.onStatusChange('disconnected');
                }
                this._attemptReconnect();
            };
            
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this._attemptReconnect();
        }
    }

    _handleMessage(event) {
        try {
            const message = JSON.parse(event.data);
            
            switch (message.type) {
                case 'ohlc':
                    if (this.onCandle && message.data) {
                        this.onCandle(message.data);
                    }
                    break;
                case 'heartbeat':
                    if (this.onHeartbeat) {
                        this.onHeartbeat(message);
                    }
                    break;
                case 'connected':
                    console.log('Server confirmed connection');
                    break;
                case 'error':
                    console.error('Server error:', message.message || message.code);
                    if (this.onError) {
                        this.onError(message);
                    }
                    break;
            }
        } catch (error) {
            console.error('Failed to parse message:', error);
        }
    }

    _attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            if (this.onStatusChange) {
                this.onStatusChange('failed');
            }
            return;
        }
        
        const delay = Math.min(
            this.baseDelay * Math.pow(2, this.reconnectAttempts),
            this.maxDelay
        );
        
        this.reconnectAttempts++;
        
        if (this.onStatusChange) {
            this.onStatusChange('reconnecting');
        }
        
        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
        
        setTimeout(() => {
            this._establishConnection();
        }, delay);
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }
}

export default WebSocketManager;