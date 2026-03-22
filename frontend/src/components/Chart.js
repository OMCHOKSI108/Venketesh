/**
 * Chart Component
 * Manages TradingView Lightweight Charts
 */

class Chart {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.chart = null;
        this.candleSeries = null;
        this.resizeObserver = null;
    }

    init() {
        if (!this.container) {
            console.error('Chart container not found');
            return;
        }

        this.chart = LightweightCharts.createChart(this.container, {
            width: this.container.clientWidth,
            height: this.container.clientHeight,
            layout: {
                background: { type: 'solid', color: '#ffffff' },
                textColor: '#333333',
            },
            grid: {
                vertLines: { color: '#e0e0e0' },
                horzLines: { color: '#e0e0e0' },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
            rightPriceScale: {
                borderColor: '#e0e0e0',
            },
            timeScale: {
                borderColor: '#e0e0e0',
                timeVisible: true,
                secondsVisible: false,
            },
        });

        this.candleSeries = this.chart.addCandlestickSeries({
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderVisible: false,
            wickUpColor: '#26a69a',
            wickDownColor: '#ef5350',
        });

        this.resizeObserver = new ResizeObserver(() => {
            if (this.chart && this.container) {
                this.chart.resize(
                    this.container.clientWidth,
                    this.container.clientHeight
                );
            }
        });
        
        this.resizeObserver.observe(this.container);
    }

    loadHistory(data) {
        if (!this.candleSeries || !data || data.length === 0) return;

        const formattedData = data.map(candle => ({
            time: this._parseTimestamp(candle.timestamp || candle.time),
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
        }));

        this.candleSeries.setData(formattedData);
        this.chart.timeScale().fitContent();
    }

    updateCandle(candle) {
        if (!this.candleSeries || !candle) return;

        const formatted = {
            time: this._parseTimestamp(candle.timestamp || candle.time),
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
        };

        this.candleSeries.update(formatted);
    }

    appendCandle(candle) {
        if (!this.candleSeries || !candle) return;
        this.updateCandle(candle);
    }

    _parseTimestamp(ts) {
        if (!ts) return Math.floor(Date.now() / 1000);
        
        if (typeof ts === 'number') {
            return ts;
        }
        
        if (typeof ts === 'string') {
            const date = new Date(ts);
            return Math.floor(date.getTime() / 1000);
        }
        
        if (ts instanceof Date) {
            return Math.floor(ts.getTime() / 1000);
        }
        
        return Math.floor(Date.now() / 1000);
    }

    destroy() {
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
        }
        if (this.chart) {
            this.chart.remove();
            this.chart = null;
        }
    }
}

export default Chart;