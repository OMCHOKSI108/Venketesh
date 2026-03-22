# DESIGN.md – Frontend System for Real-Time Market Data Visualization

## 1. Project Overview and User Goals

This project delivers a **browser‑based dashboard** that visualises real‑time and historical index data (NIFTY, BANKNIFTY, S&P 500, etc.) for development and analysis purposes. It consumes data from a FastAPI backend that implements a robust ETL pipeline with multiple data source fallbacks (Upstox → NSE unofficial → Yahoo Finance). The frontend is designed to be lightweight, production‑ready, and focused on a smooth user experience with latency tolerance of 1–5 seconds.

**Primary User Goals**  
- View live OHLC (Open, High, Low, Close) charts for selected indices.  
- Switch between symbols and timeframes (1m, 5m, 15m, etc.) seamlessly.  
- Trust that data is reliable – the UI clearly indicates the current data source and any fallback in use.  
- Experience a responsive, accessible interface that works on both desktop and tablet devices.  
- Optionally inspect basic market data (volume, last price) alongside the chart.

---

## 2. UI/UX Design Principles and Guidelines

- **Clarity over complexity** – The main chart occupies the primary visual space; controls are minimal and self‑explanatory.  
- **Real‑time feedback** – Incoming WebSocket updates are applied instantly; a connection status indicator (online / fallback / offline) is always visible.  
- **Reliability signals** – The current data source (Upstox, NSE, Yahoo) is shown, and any fallback activation is communicated without distracting the user.  
- **Consistent behaviour** – Symbol and timeframe changes reset the chart view appropriately and fetch historical data from the REST API.  
- **Performance first** – Animations and updates are throttled to avoid jank; the chart library (TradingView Lightweight Charts) is chosen for its low overhead.  
- **Accessibility** – Keyboard navigation, proper ARIA labels, and sufficient contrast ratios are enforced.

---

## 3. Information Architecture

### Pages and Screens
The application is a **single‑page dashboard** with no internal navigation. All functionality is contained in one view:

| Screen Element         | Description                                                                 |
|------------------------|-----------------------------------------------------------------------------|
| **Header Bar**         | Symbol selector, timeframe selector, data source status indicator, WebSocket connection status. |
| **Chart Area**         | Candlestick chart (TradingView Lightweight Charts) with time axis and price axis. |
| **Status Panel**       | Optional panel showing last price, volume, and current data source details. |
| **Control Bar**        | Buttons for zoom in/out, reset view, full‑screen (if needed).               |

### User Journey
1. **Initial Load**  
   - User opens `index.html`.  
   - Frontend requests historical OHLC data for the default symbol (e.g., NIFTY) from the REST endpoint `GET /ohlc/{symbol}?timeframe=1m`.  
   - A WebSocket connection is established to `ws://backend/ws/{symbol}` for live updates.  
   - Chart renders historical data, then real‑time updates begin.

2. **Symbol Change**  
   - User selects a new symbol from the dropdown.  
   - WebSocket connection is closed for the old symbol and a new connection is opened.  
   - Historical data for the new symbol is fetched.  
   - Chart is reset and re‑initialised with the new data.

3. **Timeframe Change**  
   - User selects a different timeframe (e.g., 5m).  
   - WebSocket remains connected (same symbol).  
   - Historical data for the new timeframe is fetched (the backend aggregates accordingly).  
   - The chart series is replaced with the new dataset.

4. **Data Source Fallback**  
   - If the primary data source fails, the backend automatically switches to the next available source.  
   - The frontend receives a WebSocket message (or REST response header) indicating the active source.  
   - The UI updates the source indicator (e.g., “Upstox” → “NSE fallback”) to keep the user informed.

5. **Reconnection**  
   - If the WebSocket disconnects, the UI shows a “Reconnecting…” status and attempts to reconnect with exponential backoff.  
   - Historical data remains visible during the outage.

---

## 4. Wireframe Descriptions (Low‑level Layout)

```
+------------------------------------------------------------------+
|  [ Symbol ▼ ]  [ 1m ▼ ]  [●] Source: Upstox  [🔌] WebSocket: ON |
+------------------------------------------------------------------+
|                                                                  |
|                                                                  |
|                                                                  |
|                                                                  |
|                      Candlestick Chart Area                      |
|                      (Lightweight Charts)                        |
|                                                                  |
|                                                                  |
|                                                                  |
|                                                                  |
+------------------------------------------------------------------+
|  Last: 21850.25   Volume: 1.2M   High: 21900   Low: 21820       |
+------------------------------------------------------------------+
```

- **Top Bar** – Sticky, with dropdowns and status indicators.  
- **Chart** – Occupies most of the viewport; responsive to window resize.  
- **Footer/Status Bar** – Displays auxiliary data; can be collapsed if desired.

**Responsive Behaviour**  
- On tablet/small screens, the top bar wraps into two rows, and the footer panel becomes a collapsible section.  
- Chart dimensions adapt to the container size via `ResizeObserver`.

---

## 5. Component Architecture

The frontend is built as a **modular component‑based system**, even if no framework is used. This ensures maintainability and future scalability.  

| Component               | Responsibility                                                                 |
|-------------------------|--------------------------------------------------------------------------------|
| `App`                   | Orchestrates the page, manages top‑level state, initialises WebSocket.        |
| `SymbolSelector`        | Renders a dropdown of symbols; emits `change` event.                          |
| `TimeframeSelector`     | Renders a dropdown of timeframes; emits `change` event.                       |
| `StatusIndicator`       | Displays data source and WebSocket connection state.                          |
| `Chart`                 | Encapsulates TradingView Lightweight Charts creation, update, and destruction.|
| `InfoPanel`             | Shows last price, volume, etc.                                                |
| `WebSocketManager`      | Manages connection lifecycle, reconnection, and message parsing.              |

### Component Communication
- Events: Custom DOM events or a simple pub/sub bus.  
- For a more structured approach, a **store** (see State Management) holds shared state and notifies components of changes.

---

## 6. State Management Approach and Data Flow

Given the moderate complexity, we use a **custom store pattern** with reactive updates. This avoids the overhead of a full Redux store while preserving a single source of truth.

**Store Structure**  
```javascript
const store = {
  symbol: 'NIFTY',
  timeframe: '1m',
  historicalData: [],      // array of OHLC objects
  realtimeCandle: null,    // last incomplete candle (is_closed = false)
  dataSource: 'Upstox',
  wsConnected: false,
  error: null
};
```

**Update Flow**  
1. User interaction (symbol change) → `store.setSymbol()` → `store.notify('symbol')`.  
2. Components subscribe to store changes and re‑render only relevant parts.  
3. The `Chart` component listens to `historicalData` and `realtimeCandle` to update the chart.  
4. WebSocket messages are transformed and merged into the store.  

**Data Merging Logic**  
- Historical data is loaded once and kept in the store.  
- Real‑time updates arrive every 1 second via WebSocket.  
- If the new candle has `is_closed: true`, it is appended to `historicalData` and the `realtimeCandle` is reset.  
- Otherwise, `realtimeCandle` replaces the current working candle (partial update).  

This separation prevents excessive array mutations and keeps the chart library efficient.

---

## 7. Technology Stack (Frameworks, Libraries, and Justification)

| Layer        | Choice                        | Justification                                                                                   |
|--------------|-------------------------------|-------------------------------------------------------------------------------------------------|
| **Core**     | Vanilla JavaScript (ES2020)   | Lightweight, no framework overhead; easy to embed in `index.html`. Production‑ready with modules.|
| **Build**    | Vite                           | Fast dev server, optimised production builds, and easy to migrate to a framework later.         |
| **Charting** | TradingView Lightweight Charts| Optimised for real‑time streaming, low memory footprint, and excellent candlestick rendering.   |
| **WebSocket**| Native `WebSocket` API         | No additional library needed; robust enough for the use case.                                   |
| **HTTP**     | `fetch` API                    | Modern, native, and well‑supported.                                                             |
| **Styling**  | Tailwind CSS                   | Utility‑first for rapid development, consistent design, and built‑in responsive/accessibility utilities. |
| **Testing**  | Jest + Testing Library         | (Future) For unit and integration tests.                                                        |

**Why not React/Vue?**  
While the project may eventually scale, the current phase calls for simplicity and a single HTML file. A lightweight vanilla approach keeps the initial build minimal. However, the architecture is component‑oriented, so migrating to a framework later would be straightforward.

---

## 8. Styling Strategy (CSS Methodology, Design System, Theming)

- **CSS Utility‑First with Tailwind CSS** – All styles are composed using Tailwind classes, ensuring consistency and reducing custom CSS.  
- **Design Tokens** – Tailwind config defines colours, spacing, typography, and breakpoints. This serves as a mini design system.  
- **Theming** – Support for light/dark themes is achieved by toggling a `data-theme` attribute on the `<html>` element and using Tailwind’s dark mode variant.  
- **Responsiveness** – Tailwind’s responsive prefixes (`sm:`, `md:`, `lg:`) handle layout changes.  
- **Accessibility** – Focus rings, sufficient contrast, and ARIA labels are enforced via custom CSS overrides and Tailwind’s focus utilities.

**Custom CSS (minimal)**  
- Overrides for Lightweight Charts container sizing.  
- WebSocket status dot animations.  
- Print styles (optional).

---

## 9. Responsiveness and Accessibility Considerations

### Responsiveness
- The chart container uses `width: 100%` and `height: 70vh` on desktop, scaling to `50vh` on mobile.  
- Dropdowns become full‑width on small screens and stack vertically.  
- Touch events are supported: pinch‑to‑zoom on the chart is disabled (to avoid interference), but buttons provide large tap targets.

### Accessibility
- **Keyboard navigation** – All interactive elements (dropdowns, buttons) are focusable and operable with keyboard (Enter, Space, Arrow keys).  
- **Screen readers** – `aria-label` for icons, `role="status"` for status indicators, and live regions for important announcements (e.g., data source change).  
- **Colour contrast** – Tailwind’s default palette is tested against WCAG AA standards.  
- **Reduced motion** – No animations that would cause issues for users who prefer reduced motion (respects `prefers-reduced-motion`).

---

## 10. Performance Optimization Strategies

- **WebSocket Throttling** – The backend pushes updates at 1 second intervals; the frontend does not perform additional throttling.  
- **Chart Updates** – Lightweight Charts uses canvas and efficiently updates only changed areas.  
- **Bundle Size** – Vite treeshakes unused Tailwind classes and splits code into vendor chunks.  
- **Lazy Loading** – The chart library is loaded dynamically only when the page is ready, reducing initial load time.  
- **Debounced Resize** – Chart resize is debounced using `ResizeObserver` to avoid excessive redraws.  
- **Memory Management** – The WebSocket manager cleans up listeners and re‑initialises chart series on symbol change to prevent memory leaks.

---

## 11. Integration with Backend APIs

### REST Endpoints
- `GET /ohlc/{symbol}?timeframe=1m` – Returns historical OHLC array.  
  - **Request Example**: `GET /ohlc/NIFTY?timeframe=1m`  
  - **Response**:  
    ```json
    [
      {"timestamp": 1640000000, "open": 18000, "high": 18050, "low": 17980, "close": 18020, "volume": 100000},
      ...
    ]
    ```

### WebSocket
- `ws://backend/ws/{symbol}` – Streams real‑time updates every second.  
- **Message Format**:  
  ```json
  {
    "symbol": "NIFTY",
    "timestamp": 1640000001,
    "open": 18020,
    "high": 18030,
    "low": 18015,
    "close": 18025,
    "volume": 200,
    "is_closed": false
  }
  ```

### Error Handling
- **REST** – On 4xx/5xx, show a toast notification and fallback to cached data (if any).  
- **WebSocket** – On close/error, attempt reconnection with exponential backoff; display status as “Reconnecting…” until success.

### Data Transformation
The frontend expects timestamps in Unix seconds. It converts them to the format required by Lightweight Charts (time in seconds, but the library accepts `{ time: number, ... }` directly).

---

## 12. Folder / Project Structure

```
frontend/
├── index.html                 # Entry point
├── src/
│   ├── main.js                # Application initialisation
│   ├── store.js               # Central store and pub/sub
│   ├── components/
│   │   ├── App.js
│   │   ├── Chart.js
│   │   ├── SymbolSelector.js
│   │   ├── TimeframeSelector.js
│   │   ├── StatusIndicator.js
│   │   └── InfoPanel.js
│   ├── services/
│   │   ├── api.js             # REST calls
│   │   ├── websocket.js       # WebSocket manager
│   │   └── dataMerger.js      # Merges historical and real‑time data
│   ├── utils/
│   │   ├── dom.js             # Helper functions (createElement, etc.)
│   │   ├── format.js          # Format numbers, dates
│   │   └── validation.js      # Validate incoming data (optional)
│   └── styles/
│       └── main.css           # Custom CSS (minimal, Tailwind handles most)
├── package.json
├── vite.config.js
├── tailwind.config.js
└── .eslintrc.js
```

**Build Output**  
Vite builds to `dist/` with optimised assets, ready to be served by any static server.

---

## 13. Future Enhancements and Scalability Considerations

- **Multiple Charts / Watchlist** – Add the ability to display multiple symbols simultaneously, each with its own chart instance.  
- **Technical Indicators** – Integrate lightweight indicators (SMA, EMA) via Lightweight Charts’ plugin system or a separate layer.  
- **Drawing Tools** – Extend the chart with annotation tools (trendlines, Fibonacci).  
- **User Accounts** – Save symbol preferences and custom layouts.  
- **Alerting** – Push notifications when price crosses a threshold.  
- **Migrate to a Framework** – If the feature set grows, rewrite components using React or Vue while keeping the same store and service layer.  
- **Service Worker** – Cache historical data and serve it offline.  
- **PWA** – Turn the dashboard into a progressive web app for installation on mobile devices.

**Scalability Notes**  
- The current architecture is modular, so new components can be added without affecting existing ones.  
- The store can easily be replaced with Redux or Zustand if state complexity increases.  
- WebSocket reconnection logic can be upgraded to use `backoff` and `ping/pong` mechanisms for production resilience.

---

## 14. Summary

This design document outlines a robust, production‑ready frontend for the real‑time market data dashboard. By focusing on modularity, clear state management, and performance, the system can be built incrementally and extended with confidence. The combination of TradingView Lightweight Charts, a custom store, and a flexible component architecture ensures a smooth user experience while keeping the codebase maintainable.

---

*Prepared by: Senior Frontend Architect*  
*Last updated: March 2026*