-- Market Data Platform Database Initialization

-- Core OHLC Data Table
CREATE TABLE IF NOT EXISTS ohlc_data (
    id BIGSERIAL,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    open DECIMAL(15, 4) NOT NULL,
    high DECIMAL(15, 4) NOT NULL,
    low DECIMAL(15, 4) NOT NULL,
    close DECIMAL(15, 4) NOT NULL,
    volume BIGINT,
    source VARCHAR(50) NOT NULL,
    is_closed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (symbol, timestamp, timeframe)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_ohlc_symbol_time ON ohlc_data (symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ohlc_timeframe ON ohlc_data (timeframe, timestamp DESC);

-- Symbols/Instruments metadata
CREATE TABLE IF NOT EXISTS symbols (
    symbol VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    instrument_type VARCHAR(20) NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',
    is_active BOOLEAN DEFAULT TRUE,
    additional_info JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Data source health tracking
CREATE TABLE IF NOT EXISTS source_health (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,
    failure_count INT DEFAULT 0,
    latency_ms INT,
    additional_info JSONB,
    checked_at TIMESTAMPTZ DEFAULT NOW()
);

-- ETL job tracking
CREATE TABLE IF NOT EXISTS etl_jobs (
    id SERIAL PRIMARY KEY,
    job_type VARCHAR(50) NOT NULL,
    symbol VARCHAR(20),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'running',
    records_processed INT DEFAULT 0,
    error_message TEXT,
    additional_info JSONB
);

-- API request logging (for rate limiting and analytics)
CREATE TABLE IF NOT EXISTS api_requests (
    id BIGSERIAL PRIMARY KEY,
    client_id VARCHAR(100),
    endpoint VARCHAR(255),
    method VARCHAR(10),
    status_code INT,
    response_time_ms INT,
    requested_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_requests_time ON api_requests (requested_at DESC);

-- Insert default symbols
INSERT INTO symbols (symbol, name, exchange, instrument_type, is_active) VALUES
    ('NIFTY', 'NIFTY 50', 'NSE', 'INDEX', true),
    ('BANKNIFTY', 'NIFTY BANK', 'NSE', 'INDEX', true),
    ('SENSEX', 'BSE Sensex', 'BSE', 'INDEX', true),
    ('NIFTYSENSEX', 'NIFTY 50', 'NSE', 'INDEX', true)
ON CONFLICT (symbol) DO NOTHING;
