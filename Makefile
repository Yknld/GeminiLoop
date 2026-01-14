.PHONY: help install test run demo clean preview setup

help:
	@echo "GeminiLoop - Makefile Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup          - Complete setup (install deps + browsers)"
	@echo "  make install        - Install Python and Node.js dependencies"
	@echo "  make test-setup     - Verify installation"
	@echo ""
	@echo "Development:"
	@echo "  make test           - Test lifecycle components"
	@echo "  make run            - Run orchestrator with default task"
	@echo "  make demo           - Run demo (interactive menu)"
	@echo "  make preview        - Start preview server"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean          - Remove runs/ and __pycache__"
	@echo "  make clean-all      - Remove runs/, cache, and node_modules"
	@echo "  make view-runs      - List all runs"
	@echo ""

setup: install
	@echo "Installing Playwright browsers..."
	npx playwright install chromium
	@echo ""
	@echo "✅ Setup complete!"
	@echo "Next: cp .env.example .env && edit .env"

install:
	@echo "Installing Python dependencies..."
	pip install -r requirements.txt
	@echo ""
	@echo "Installing Node.js dependencies..."
	npm install
	@echo ""

test-setup:
	@echo "Running setup verification..."
	python test_setup.py

test:
	@echo "Running all tests..."
	python3 test_setup.py
	python3 test_lifecycle.py
	python3 test_openhands.py
	python3 test_evaluator.py
	python3 test_github_client.py
	python3 test_manifest.py

test:
	@echo "Running lifecycle tests..."
	python test_lifecycle.py
	@echo ""
	@echo "Running OpenHands tests..."
	python test_openhands.py
	@echo ""
	@echo "Running evaluator tests..."
	python test_evaluator.py

run:
	@echo "Running orchestrator with default task..."
	python -m orchestrator.main "Create a beautiful landing page with hero section and CTA button"

demo:
	@echo "Running demo..."
	python demo.py list
	@echo ""
	@echo "To run a demo: make demo-0, demo-1, etc."

demo-0:
	python demo.py 0

demo-1:
	python demo.py 1

demo-2:
	python demo.py 2

preview:
	@echo "Starting preview server on http://localhost:8080..."
	python services/preview_server.py

clean:
	@echo "Cleaning up runs/ and cache..."
	rm -rf runs/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✅ Cleaned"

clean-all: clean
	@echo "Removing node_modules..."
	rm -rf node_modules/
	@echo "✅ Full clean complete"

view-runs:
	@echo "Listing all runs..."
	@if [ -d "runs" ]; then \
		ls -lt runs/ | head -20; \
	else \
		echo "No runs directory found"; \
	fi

# Docker commands
docker-build:
	@echo "Building Docker image..."
	docker build -f deploy/runpod/Dockerfile -t gemini-loop:latest .

docker-run:
	@echo "Running Docker container..."
	docker run -p 8080:8080 \
		-e GOOGLE_AI_STUDIO_API_KEY=${GOOGLE_AI_STUDIO_API_KEY} \
		-v $(PWD)/runs:/app/runs \
		gemini-loop:latest

docker-run-visible:
	@echo "Running Docker container with visible browser..."
	docker run -p 8080:8080 -p 6080:6080 \
		-e GOOGLE_AI_STUDIO_API_KEY=${GOOGLE_AI_STUDIO_API_KEY} \
		-e VISIBLE_BROWSER=1 \
		-v $(PWD)/runs:/app/runs \
		gemini-loop:latest
	@echo ""
	@echo "Browser view: http://localhost:6080/vnc.html (password: secret)"

# Development helpers
lint:
	@echo "Running Python linters..."
	@command -v pylint >/dev/null 2>&1 && pylint orchestrator/ || echo "pylint not installed"
	@command -v flake8 >/dev/null 2>&1 && flake8 orchestrator/ || echo "flake8 not installed"

format:
	@echo "Formatting Python code..."
	@command -v black >/dev/null 2>&1 && black orchestrator/ services/ || echo "black not installed"

dev:
	@echo "Starting development environment..."
	@echo "1. Preview server on http://localhost:8080"
	@echo "2. Ready to run: python -m orchestrator.main 'Your task'"
	python services/preview_server.py
