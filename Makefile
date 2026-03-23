.PHONY: help install dev up down build logs clean test rebuild

help:
	@echo "Market Data Platform - Available Commands"
	@echo ""
	@echo "  make install    - Install Python dependencies"
	@echo "  make dev       - Run development server"
	@echo "  make up        - Build and start Docker containers"
	@echo "  make down      - Stop Docker containers"
	@echo "  make build     - Rebuild Docker images"
	@echo "  make logs      - View container logs"
	@echo "  make clean     - Remove containers and volumes"
	@echo "  make rebuild   - Rebuild Docker images and restart services"

install:
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

up:
	docker-compose up --build -d

down:
	docker-compose down

build:
	docker-compose build --no-cache

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	rm -rf __pycache__ app/__pycache__ app/**/__pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

test:
	pytest tests/ -v

lint:
	ruff check app/

rebuild:
	docker-compose down && docker-compose up -d --build --remove-orphans
