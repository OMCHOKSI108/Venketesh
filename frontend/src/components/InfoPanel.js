/**
 * InfoPanel Component
 * Displays last price, volume, daily high/low
 */

class InfoPanel {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.data = null;
    }

    init() {
        if (!this.container) {
            console.error('InfoPanel container not found');
            return;
        }
        
        this.render();
    }

    update(candle) {
        if (!candle) return;
        
        this.data = {
            lastPrice: candle.close,
            open: candle.open,
            high: candle.high,
            low: candle.low,
            volume: candle.volume || 0,
            timestamp: candle.timestamp,
        };
        
        this.render();
    }

    render() {
        if (!this.container || !this.data) return;
        
        const d = this.data;
        const priceChange = d.lastPrice - d.open;
        const priceChangePercent = d.open > 0 ? (priceChange / d.open * 100).toFixed(2) : 0;
        const isPositive = priceChange >= 0;
        
        this.container.innerHTML = `
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-slate-800 rounded-lg">
                <div class="text-center">
                    <div class="text-xs text-slate-400 uppercase">Last Price</div>
                    <div class="text-xl font-bold ${isPositive ? 'text-green-400' : 'text-red-400'}">
                        ${d.lastPrice.toFixed(2)}
                    </div>
                </div>
                <div class="text-center">
                    <div class="text-xs text-slate-400 uppercase">Change</div>
                    <div class="text-xl font-bold ${isPositive ? 'text-green-400' : 'text-red-400'}">
                        ${isPositive ? '+' : ''}${priceChange.toFixed(2)} (${priceChangePercent}%)
                    </div>
                </div>
                <div class="text-center">
                    <div class="text-xs text-slate-400 uppercase">Day High</div>
                    <div class="text-xl font-bold text-green-400">${d.high.toFixed(2)}</div>
                </div>
                <div class="text-center">
                    <div class="text-xs text-slate-400 uppercase">Day Low</div>
                    <div class="text-xl font-bold text-red-400">${d.low.toFixed(2)}</div>
                </div>
            </div>
        `;
    }

    destroy() {
        this.container = null;
        this.data = null;
    }
}

export default InfoPanel;