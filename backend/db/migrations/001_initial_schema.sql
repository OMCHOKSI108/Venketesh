-- Migration: 001_initial_schema.sql
-- Phase: 3.1 PostgreSQL Setup
-- Description: Create all tables for market data platform

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Core OHLC Data Table (TimescaleDB hypertable)
CREATE TABLE IF NOT EXISTS ohlc_data (
    id BIGSERIAL,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    timeframe VARCHAR(10) NOT NULL DEFAULT '1m',
    open DECIMAL(15, 4) NOT NULL,
    high DECIMAL(15, 4) NOT NULL,
    low DECIMAL(15, 4) NOT NULL,
    close DECIMAL(15, 4) NOT NULL,
    volume BIGINT,
    source VARCHAR(50) NOT NULL,
    is_closed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (symbol, timestamp, timeframe)
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('ohlc_data', 'timestamp', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_ohlc_symbol_time 
    ON ohlc_data (symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ohlc_timeframe 
    ON ohlc_data (timeframe, timestamp DESC);

-- Symbols/Instruments metadata
CREATE TABLE IF NOT EXISTS symbols (
    symbol VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    exchange VARCHAR(20) NOT NULL DEFAULT 'NSE',
    instrument_type VARCHAR(20) NOT NULL DEFAULT 'INDEX',
    currency VARCHAR(3) DEFAULT 'INR',
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Data source health tracking
CREATE TABLE IF NOT EXISTS source_health (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'unknown',
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,
    failure_count INT DEFAULT 0,
    latency_ms INT,
    metadata JSONB,
    checked_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_name)
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
    metadata JSONB
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

-- Convert to hypertable
SELECT create_hypertable('api_requests', 'requested_at',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE);

-- Seed symbols table
INSERT INTO symbols (symbol, name, exchange, instrument_type) VALUES
    ('NIFTY', 'NIFTY 50', 'NSE', 'INDEX'),
    ('BANKNIFTY', 'NIFTY BANK', 'NSE', 'INDEX'),
    ('SENSEX', 'SENSEX', 'BSE', 'INDEX')
ON CONFLICT (symbol) DO NOTHING;

-- Grant permissions (adjust as needed for your setup)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;