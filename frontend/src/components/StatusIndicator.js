/**
 * Status Indicator Component
 * Shows connection status and data source
 */

class StatusIndicator {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.statusDot = null;
        this.sourceLabel = null;
    }

    init() {
        if (!this.container) {
            console.error('StatusIndicator container not found');
            return;
        }

        this.statusDot = this.container.querySelector('.status-dot');
        this.sourceLabel = this.container.querySelector('.source-label');
    }

    update(state) {
        if (this.statusDot) {
            this.statusDot.classList.remove(
                'bg-green-500',
                'bg-yellow-500',
                'bg-red-500',
                'bg-gray-500'
            );

            switch (state.wsStatus) {
                case 'connected':
                    this.statusDot.classList.add('bg-green-500', 'animate-pulse');
                    break;
                case 'reconnecting':
                    this.statusDot.classList.add('bg-yellow-500', 'animate-pulse');
                    break;
                case 'disconnected':
                case 'failed':
                default:
                    this.statusDot.classList.add('bg-red-500');
                    break;
            }
        }

        if (this.sourceLabel) {
            let statusText = '';
            switch (state.wsStatus) {
                case 'connected':
                    statusText = 'Live';
                    break;
                case 'reconnecting':
                    statusText = 'Reconnecting...';
                    break;
                case 'disconnected':
                case 'failed':
                default:
                    statusText = 'Offline';
                    break;
            }

            if (state.dataSource && state.dataSource !== 'unknown') {
                statusText += ` (${state.dataSource})`;
            }

            this.sourceLabel.textContent = statusText;
        }
    }

    destroy() {
        this.container = null;
        this.statusDot = null;
        this.sourceLabel = null;
    }
}

export default StatusIndicator;